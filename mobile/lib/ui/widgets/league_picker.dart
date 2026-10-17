import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../data/app_state.dart';
import '../../data/repository.dart';

/// League selector shared by Matches and Standings. Defaults to the demo league.
class LeaguePicker extends StatefulWidget {
  const LeaguePicker({super.key});

  @override
  State<LeaguePicker> createState() => _LeaguePickerState();
}

class _LeaguePickerState extends State<LeaguePicker> {
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final s = context.read<AppState>();
    try {
      final l = await s.repo.leagues();
      final items = asList(asMap(l.data)['items']);
      s.leagues = items;
      if (items.isNotEmpty && !items.any((i) => i['league_id'] == s.leagueId)) {
        await s.setLeague(items.first['league_id'] as String);
      }
      if (mounted) setState(() {});
      await s.repo.prefetchSport(s.sportIdFor(s.leagueId));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    if (s.leagues.length < 2) {
      final name = s.leagues.isEmpty ? null : s.leagues.first['name'] as String?;
      if (name == null) return const SizedBox.shrink();
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
        child: Text(name, style: Theme.of(context).textTheme.titleMedium),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: DropdownButtonFormField<String>(
        key: ValueKey(s.leagueId),
        initialValue: s.leagueId,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'League', isDense: true),
        items: [
          for (final l in s.leagues)
            DropdownMenuItem(
              value: l['league_id'] as String,
              child: Text('${l['name'] ?? l['league_id']}', overflow: TextOverflow.ellipsis),
            ),
        ],
        onChanged: (v) async {
          if (v == null) return;
          await s.setLeague(v);
          await s.repo.prefetchSport(s.sportIdFor(v));
        },
      ),
    );
  }
}
