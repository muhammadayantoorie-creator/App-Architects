import 'package:flutter/material.dart';

import '../../core/formatters.dart';
import '../../core/theme.dart';

/// Android's built-in condensed family (falls back to the default font elsewhere).
const condensedFont = 'sans-serif-condensed';

const _badgePalette = [
  Color(0xFF1565C0), Color(0xFFC62828), Color(0xFF2E7D32), Color(0xFF6A1B9A), Color(0xFFEF6C00),
  Color(0xFF00838F), Color(0xFFAD1457), Color(0xFF4E342E), Color(0xFF283593), Color(0xFF558B2F),
];

String initials(String name) {
  final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  return parts.take(2).map((p) => p[0].toUpperCase()).join();
}

/// Coloured initials badge for a team (colour fixed per team id).
class TeamBadge extends StatelessWidget {
  const TeamBadge({
    super.key,
    required this.teamId,
    required this.name,
    this.size = 32,
    this.showName = true,
    this.light = false,
    this.bold = false,
    this.dim = false,
  });

  final String teamId;
  final String name;
  final double size;
  final bool showName;
  final bool light;
  final bool bold;
  final bool dim;

  @override
  Widget build(BuildContext context) {
    final color = _badgePalette[teamId.hashCode.abs() % _badgePalette.length];
    final badge = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: light ? Border.all(color: Colors.white, width: 2) : null,
      ),
      alignment: Alignment.center,
      child: Text(initials(name),
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: size * 0.38)),
    );
    if (!showName) return Semantics(label: name, child: ExcludeSemantics(child: badge));
    return Semantics(
      label: name,
      child: ExcludeSemantics(
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          badge,
          const SizedBox(width: 10),
          Flexible(
            child: Text(
              name,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 15,
                fontWeight: bold ? FontWeight.w800 : (dim ? FontWeight.w400 : FontWeight.w600),
                color: light ? Colors.white : (dim ? AppColors.textSub : AppColors.textMain),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

/// Match status as a coloured pill with text (never colour alone).
class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.status, this.time});
  final String? status;
  final DateTime? time;

  @override
  Widget build(BuildContext context) {
    final (bg, fg, label, dot) = switch (status) {
      'in_progress' => (AppColors.primary, AppColors.onPrimary, 'Live', true),
      'completed' => (AppColors.chip, Colors.white, 'FT', false),
      'upcoming' => (Colors.white, AppColors.onPrimary, time == null ? 'UPCOMING' : hm(time!), false),
      _ => (const Color(0xFFFFC107), Colors.black, humanize(status).toUpperCase(), false),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (dot) ...[
          Container(width: 7, height: 7, decoration: const BoxDecoration(color: AppColors.live, shape: BoxShape.circle)),
          const SizedBox(width: 4),
        ],
        Text(label,
            style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.5)),
      ]),
    );
  }
}

/// Big "Explore / LEAGUES" title. Hidden on short screens (e.g. landscape) to keep lists usable.
class ExploreHeading extends StatelessWidget {
  const ExploreHeading(this.word, {super.key});
  final String word;

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.sizeOf(context).height < 560) return const SizedBox.shrink();
    return Semantics(
      header: true,
      label: 'Explore $word',
      child: ExcludeSemantics(
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Explore',
                style: TextStyle(
                    color: AppColors.textSub, fontSize: 30, fontWeight: FontWeight.w300, height: 1.1)),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                word.toUpperCase(),
                style: const TextStyle(
                    fontFamily: condensedFont,
                    color: Colors.white,
                    fontSize: 72,
                    fontWeight: FontWeight.w900,
                    height: 1.0,
                    letterSpacing: -2),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 6),
        child: Text(text.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppColors.textSub)),
      );
}

class ScoreText extends StatelessWidget {
  const ScoreText(this.value, {super.key, this.big = false, this.color, this.dim = false});
  final String value;
  final bool big;
  final Color? color;
  final bool dim;

  @override
  Widget build(BuildContext context) => Text(
        value,
        style: TextStyle(
          fontSize: big ? 34 : 18,
          fontWeight: dim ? FontWeight.w400 : FontWeight.w800,
          color: color ?? (dim ? AppColors.textSub : AppColors.textMain),
          fontFeatures: const [FontFeature.tabularFigures()],
        ),
      );
}
