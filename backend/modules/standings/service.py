"""Event-log based standings, tie-breaks, and qualification status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.errors import ApiError
from backend.core.signing import lots_key
from backend.modules.events.service import score_match
from backend.modules.leagues.models import League, LeagueTeam, MatchStream
from backend.modules.sports.models import Sport


@dataclass(frozen=True)
class MatchRecord:
    home_team_id: str
    away_team_id: str
    home_score: int
    away_score: int
    home_wickets: int | None
    away_wickets: int | None
    home_balls: int | None
    away_balls: int | None
    home_fair_play: int
    away_fair_play: int
    status: str
    outcome: str
    winner_team_id: str | None

    @property
    def played(self) -> bool:
        return self.status == "completed" and self.outcome != "undecided"


def _not_found(league_id: str) -> ApiError:
    return ApiError(
        404,
        "LEAGUE_NOT_FOUND",
        f"League {league_id} was not found.",
        {"league_id": league_id},
    )


def _record(projection: dict[str, Any]) -> MatchRecord:
    home = projection["home"]
    away = projection["away"]
    return MatchRecord(
        home_team_id=home["team_id"],
        away_team_id=away["team_id"],
        home_score=home["score"],
        away_score=away["score"],
        home_wickets=home["wickets"],
        away_wickets=away["wickets"],
        home_balls=home["balls"],
        away_balls=away["balls"],
        home_fair_play=home["fair_play"],
        away_fair_play=away["fair_play"],
        status=projection["status"],
        outcome=projection["outcome"],
        winner_team_id=projection["winner_team_id"],
    )


def _score_for(match: MatchRecord, team_id: str) -> tuple[int, int]:
    if team_id == match.home_team_id:
        return match.home_score, match.away_score
    return match.away_score, match.home_score


def _points_for(
    match: MatchRecord, team_id: str, points: dict[str, int]
) -> int:
    if match.outcome == "draw":
        return points["draw"]
    if match.winner_team_id == team_id:
        return points["win"]
    return points["loss"]


def _overs_faced(match: MatchRecord, team_id: str, sport: Sport) -> float:
    periods = sport.config["periods"]
    wickets_per_innings = periods["wickets_per_innings"]
    max_overs = periods["overs_per_innings"] * periods["innings_per_team"]
    max_wickets = wickets_per_innings * periods["innings_per_team"]
    if team_id == match.home_team_id:
        balls, wickets = match.home_balls or 0, match.home_wickets or 0
    else:
        balls, wickets = match.away_balls or 0, match.away_wickets or 0
    if wickets >= max_wickets:
        return float(max_overs)
    return balls / periods["balls_per_over"]


def _innings_diff(
    team_id: str, matches: list[MatchRecord], sport: Sport
) -> float:
    runs_for = 0
    runs_against = 0
    overs_faced = 0.0
    overs_bowled = 0.0
    for match in matches:
        if team_id not in {match.home_team_id, match.away_team_id}:
            continue
        scored, conceded = _score_for(match, team_id)
        opponent_id = (
            match.away_team_id
            if team_id == match.home_team_id
            else match.home_team_id
        )
        runs_for += scored
        runs_against += conceded
        overs_faced += _overs_faced(match, team_id, sport)
        overs_bowled += _overs_faced(match, opponent_id, sport)
    run_rate_for = runs_for / overs_faced if overs_faced else 0.0
    run_rate_against = runs_against / overs_bowled if overs_bowled else 0.0
    return round(run_rate_for - run_rate_against, 3)


def _diff_for_matches(
    team_id: str, matches: list[MatchRecord], sport: Sport
) -> int | float:
    if sport.scoring_model == "innings":
        return _innings_diff(team_id, matches, sport)
    return sum(
        _score_for(match, team_id)[0] - _score_for(match, team_id)[1]
        for match in matches
        if team_id in {match.home_team_id, match.away_team_id}
    )


def _qualification_statuses(
    team_ids: list[str],
    stats: dict[str, dict[str, Any]],
    win_points: int,
    spots: int,
) -> dict[str, str]:
    maximum = {
        team_id: stats[team_id]["points"] + win_points * stats[team_id]["remaining"]
        for team_id in team_ids
    }
    statuses: dict[str, str] = {}
    for team_id in team_ids:
        clinch_threats = sum(
            1
            for other_id in team_ids
            if other_id != team_id and maximum[other_id] >= stats[team_id]["points"]
        )
        eliminated_by = sum(
            1
            for other_id in team_ids
            if other_id != team_id and stats[other_id]["points"] > maximum[team_id]
        )
        if clinch_threats < spots:
            statuses[team_id] = "clinched"
        elif eliminated_by >= spots:
            statuses[team_id] = "eliminated"
        else:
            statuses[team_id] = "still_possible"
    return statuses


def _resolve_tied_group(
    group: list[str],
    criteria: list[str],
    stats: dict[str, dict[str, Any]],
    played_matches: list[MatchRecord],
    league: League,
    sport: Sport,
) -> tuple[list[str], dict[str, str | None]]:
    """Order teams level on points; return the order and, per team, the
    criterion that finally separated it from the rest of its tied group.

    h2h criteria are evaluated in a mini-league of the tied teams only. When a
    criterion splits the group, every still-tied subgroup restarts from the
    first criterion with its own (smaller) mini-league.
    """
    if len(group) <= 1:
        return list(group), {}

    members = set(group)
    mini_league = [
        match
        for match in played_matches
        if match.home_team_id in members and match.away_team_id in members
    ]
    for criterion in criteria:
        values: dict[str, Any] = {}
        for team_id in group:
            if criterion == "h2h_points":
                values[team_id] = sum(
                    _points_for(match, team_id, league.points)
                    for match in mini_league
                    if team_id in {match.home_team_id, match.away_team_id}
                )
            elif criterion == "h2h_diff":
                values[team_id] = _diff_for_matches(team_id, mini_league, sport)
            elif criterion == "overall_diff":
                values[team_id] = stats[team_id]["diff"]
            elif criterion == "scored":
                values[team_id] = stats[team_id]["scored"]
            elif criterion == "fair_play":
                values[team_id] = stats[team_id]["fair_play"]
            else:  # draw_lots: ascending SHA-256 key
                values[team_id] = lots_key(
                    league.lots_seed, league.league_id, team_id
                )

        buckets: dict[Any, list[str]] = {}
        for team_id in group:
            buckets.setdefault(values[team_id], []).append(team_id)
        if len(buckets) == 1:
            continue

        ordered: list[str] = []
        resolved: dict[str, str | None] = {}
        for value in sorted(buckets, reverse=criterion != "draw_lots"):
            child = buckets[value]
            if len(child) == 1:
                ordered.append(child[0])
                resolved[child[0]] = criterion
                continue
            child_order, child_resolved = _resolve_tied_group(
                child, criteria, stats, played_matches, league, sport
            )
            ordered.extend(child_order)
            resolved.update(child_resolved)
        return ordered, resolved

    # Only reachable on a SHA-256 collision in draw_lots; keep a stable order.
    return sorted(group), {team_id: None for team_id in group}


def get_standings(session: Session, league_id: str) -> dict[str, Any]:
    league = session.get(League, league_id)
    if league is None:
        raise _not_found(league_id)
    sport = session.get(Sport, league.sport_id)
    if sport is None:
        raise ApiError(
            404,
            "SPORT_NOT_FOUND",
            f"Sport {league.sport_id} was not found.",
            {"sport_id": league.sport_id},
        )

    team_ids = list(
        session.scalars(
            select(LeagueTeam.team_id)
            .where(LeagueTeam.league_id == league_id)
            .order_by(LeagueTeam.team_id)
        ).all()
    )
    streams = list(
        session.scalars(
            select(MatchStream)
            .where(MatchStream.league_id == league_id)
            .order_by(MatchStream.match_id)
        ).all()
    )
    matches = [
        _record(score_match(session, stream.match_id)) for stream in streams
    ]
    played_matches = [match for match in matches if match.played]

    stats: dict[str, dict[str, Any]] = {
        team_id: {
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "scored": 0,
            "conceded": 0,
            "points": 0,
            "fair_play": 0,
            "remaining": 0,
            "diff": 0,
        }
        for team_id in team_ids
    }
    h2h = {
        team_id: {
            opponent_id: {"played": 0, "points": 0, "scored": 0, "conceded": 0}
            for opponent_id in team_ids
            if opponent_id != team_id
        }
        for team_id in team_ids
    }

    for match in matches:
        home_id = match.home_team_id
        away_id = match.away_team_id
        if match.status != "completed":
            # Still to be decided: counts towards each side's maximum points.
            if home_id in stats:
                stats[home_id]["remaining"] += 1
            if away_id in stats:
                stats[away_id]["remaining"] += 1
            continue
        # Only completed matches with an outcome other than undecided count.
        if not match.played:
            continue

        if home_id not in stats or away_id not in stats:
            continue
        home_stat = stats[home_id]
        away_stat = stats[away_id]
        home_stat["fair_play"] += match.home_fair_play
        away_stat["fair_play"] += match.away_fair_play
        home_stat["played"] += 1
        away_stat["played"] += 1
        home_stat["scored"] += match.home_score
        home_stat["conceded"] += match.away_score
        away_stat["scored"] += match.away_score
        away_stat["conceded"] += match.home_score

        if match.outcome == "draw":
            home_stat["drawn"] += 1
            away_stat["drawn"] += 1
            home_stat["points"] += league.points["draw"]
            away_stat["points"] += league.points["draw"]
            home_h2h_points = away_h2h_points = league.points["draw"]
        else:
            winner = match.winner_team_id
            loser_id = away_id if winner == home_id else home_id
            stats[winner]["won"] += 1
            stats[loser_id]["lost"] += 1
            stats[winner]["points"] += league.points["win"]
            stats[loser_id]["points"] += league.points["loss"]
            home_h2h_points = _points_for(match, home_id, league.points)
            away_h2h_points = _points_for(match, away_id, league.points)

        home_h2h = h2h[home_id][away_id]
        away_h2h = h2h[away_id][home_id]
        home_h2h["played"] += 1
        home_h2h["points"] += home_h2h_points
        home_h2h["scored"] += match.home_score
        home_h2h["conceded"] += match.away_score
        away_h2h["played"] += 1
        away_h2h["points"] += away_h2h_points
        away_h2h["scored"] += match.away_score
        away_h2h["conceded"] += match.home_score

    for team_id in team_ids:
        if sport.scoring_model == "innings":
            stats[team_id]["diff"] = _innings_diff(team_id, played_matches, sport)
        else:
            stats[team_id]["diff"] = (
                stats[team_id]["scored"] - stats[team_id]["conceded"]
            )

    criteria = [
        item for item in league.tie_break_order if item != "draw_lots"
    ] + ["draw_lots"]
    by_points: dict[int, list[str]] = {}
    for team_id in team_ids:
        by_points.setdefault(stats[team_id]["points"], []).append(team_id)

    ranked: list[str] = []
    resolved_by: dict[str, str | None] = {}
    for points_value in sorted(by_points, reverse=True):
        group = by_points[points_value]
        ordered, resolved = _resolve_tied_group(
            group, criteria, stats, played_matches, league, sport
        )
        for team_id in ordered:
            # null for a team that was never level on points with another.
            resolved_by[team_id] = resolved.get(team_id)
        ranked.extend(ordered)

    qualification = _qualification_statuses(
        team_ids, stats, league.points["win"], league.qualification_spots
    )
    table = [
        {
            "rank": rank,
            "team_id": team_id,
            "played": stats[team_id]["played"],
            "won": stats[team_id]["won"],
            "drawn": stats[team_id]["drawn"],
            "lost": stats[team_id]["lost"],
            "scored": stats[team_id]["scored"],
            "conceded": stats[team_id]["conceded"],
            "diff": stats[team_id]["diff"],
            "points": stats[team_id]["points"],
            "fair_play": stats[team_id]["fair_play"],
            "status": qualification[team_id],
            "resolved_by": resolved_by[team_id],
        }
        for rank, team_id in enumerate(ranked, start=1)
    ]

    return {
        "league_id": league.league_id,
        "sport_id": league.sport_id,
        "qualification_spots": league.qualification_spots,
        "table": table,
        "h2h": h2h,
    }
