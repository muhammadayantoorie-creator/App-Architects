import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../data/app_state.dart';
import 'screens/club.dart';
import 'screens/fixtures.dart';
import 'screens/outbox.dart';
import 'screens/scoring.dart';
import 'screens/settings.dart';
import 'screens/standings.dart';
import 'screens/store.dart';
import 'widgets/network_chip.dart';

class _TenantLogo extends StatelessWidget {
  const _TenantLogo({required this.url, required this.name});
  final String? url;
  final String name;

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final fallback = CircleAvatar(
      radius: 18,
      backgroundColor: s.primary,
      child: Text(name.isEmpty ? '?' : name[0].toUpperCase(),
          style: TextStyle(color: s.onPrimary, fontWeight: FontWeight.w900),
          semanticsLabel: '$name logo'),
    );
    if (url == null || url!.isEmpty) return Center(child: fallback);
    return Center(
      child: ClipOval(
        child: Image.network(
          url!,
          width: 36,
          height: 36,
          fit: BoxFit.cover,
          semanticLabel: '$name logo',
          errorBuilder: (_, _, _) => fallback,
        ),
      ),
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    // Role-aware home: managers and players land on their club, everyone else on matches.
    if (const ['club_manager', 'player'].contains(context.read<AppState>().role)) _index = 3;
  }

  void _open(Widget screen) =>
      Navigator.push(context, MaterialPageRoute<void>(builder: (_) => screen));

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(
        leading: Padding(
          padding: const EdgeInsets.only(left: 12),
          child: _TenantLogo(url: s.tenant['logo_url'] as String?, name: s.tenantName),
        ),
        leadingWidth: 52,
        title: Text(s.tenantName, overflow: TextOverflow.ellipsis),
        titleSpacing: 8,
        actions: [
          const NetworkChip(),
          PopupMenuButton<String>(
            tooltip: 'More options',
            icon: const CircleAvatar(
              radius: 22,
              backgroundColor: AppColors.chip,
              child: Icon(Icons.more_horiz, color: Colors.white, semanticLabel: 'More options'),
            ),
            onSelected: (v) => switch (v) {
              'outbox' => _open(const OutboxScreen()),
              'scoring' => _open(ScoringScreen(leagueId: s.leagueId)),
              'settings' => _open(const SettingsScreen()),
              'signout' => confirmSignOut(context),
              _ => null,
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                  value: 'outbox',
                  child: ListTile(leading: Icon(Icons.outbox), title: Text('Outbox'))),
              if (s.canScore)
                const PopupMenuItem(
                    value: 'scoring',
                    child: ListTile(leading: Icon(Icons.scoreboard), title: Text('Scoring'))),
              const PopupMenuItem(
                  value: 'settings',
                  child: ListTile(leading: Icon(Icons.settings), title: Text('Settings'))),
              const PopupMenuItem(
                  value: 'signout',
                  child: ListTile(leading: Icon(Icons.logout), title: Text('Sign out'))),
            ],
          ),
        ],
      ),
      body: SafeArea(
        top: false,
        bottom: false,
        child: switch (_index) {
          0 => const FixturesTab(),
          1 => const StandingsTab(),
          2 => const StoreTab(),
          _ => const ClubTab(),
        },
      ),
      bottomNavigationBar: _PillNav(index: _index, onTap: (i) => setState(() => _index = i)),
    );
  }
}

/// Floating black pill navigation: lime pill for the current tab, dark circles for the rest.
class _PillNav extends StatelessWidget {
  const _PillNav({required this.index, required this.onTap});
  final int index;
  final ValueChanged<int> onTap;

  static const _items = [
    (Icons.home_outlined, Icons.home_rounded, 'Matches'),
    (Icons.leaderboard_outlined, Icons.leaderboard, 'Standings'),
    (Icons.storefront_outlined, Icons.storefront, 'Store'),
    (Icons.groups_outlined, Icons.groups, 'Club'),
  ];

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 12),
        child: Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: const Color(0xFF151517),
            borderRadius: BorderRadius.circular(40),
            border: Border.all(color: AppColors.chip),
          ),
          child: Row(children: [
            for (var i = 0; i < _items.length; i++)
              Expanded(
                flex: i == index ? 2 : 1,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: Semantics(
                    button: true,
                    selected: i == index,
                    label: _items[i].$3,
                    child: ExcludeSemantics(
                      child: Tooltip(
                        message: _items[i].$3,
                        child: Material(
                          color: i == index ? AppColors.primary : AppColors.chip,
                          shape: const StadiumBorder(),
                          child: InkWell(
                            customBorder: const StadiumBorder(),
                            onTap: () => onTap(i),
                            child: SizedBox(
                              height: 54,
                              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                                Icon(i == index ? _items[i].$2 : _items[i].$1,
                                    size: 26,
                                    color: i == index ? AppColors.onPrimary : Colors.white),
                                if (i == index) ...[
                                  const SizedBox(width: 6),
                                  Flexible(
                                    child: Text(_items[i].$3,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                            color: AppColors.onPrimary,
                                            fontWeight: FontWeight.w800,
                                            fontSize: 14)),
                                  ),
                                ],
                              ]),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
          ]),
        ),
      ),
    );
  }
}
