import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme.dart';
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
    // Green strip continuing the header, with one white chip per league.
    return Container(
      width: double.infinity,
      color: AppColors.bg,
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
      child: s.leagues.isEmpty
          ? const SizedBox(height: 4)
          : SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(children: [
                for (final l in s.leagues)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: Builder(builder: (context) {
                      final selected = l['league_id'] == s.leagueId;
                      return ChoiceChip(
                        label: Text('${l['name'] ?? l['league_id']}'),
                        selected: selected,
                        showCheckmark: false,
                        backgroundColor: AppColors.chip,
                        selectedColor: AppColors.primary,
                        side: BorderSide.none,
                        shape: const StadiumBorder(),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        labelStyle: TextStyle(
                          color: selected ? AppColors.onPrimary : Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                        onSelected: (_) async {
                          final id = l['league_id'] as String;
                          await s.setLeague(id);
                          await s.repo.prefetchSport(s.sportIdFor(id));
                        },
                      );
                    }),
                  ),
              ]),
            ),
    );
  }
}
