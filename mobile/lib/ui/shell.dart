import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../data/app_state.dart';
import 'screens/club.dart';
import 'screens/fixtures.dart';
import 'screens/outbox.dart';
import 'screens/scoring.dart';
import 'screens/settings.dart';
import 'screens/standings.dart';
import 'screens/store.dart';
import 'widgets/network_chip.dart';

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _index = 0;

  void _open(Widget screen) =>
      Navigator.push(context, MaterialPageRoute<void>(builder: (_) => screen));

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(
        title: Text(s.tenantName, overflow: TextOverflow.ellipsis),
        titleSpacing: 16,
        actions: [
          const NetworkChip(),
          PopupMenuButton<String>(
            tooltip: 'More options',
            icon: const Icon(Icons.more_vert, semanticLabel: 'More options'),
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
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.event_outlined, semanticLabel: 'Matches'),
              selectedIcon: Icon(Icons.event, semanticLabel: 'Matches'),
              label: 'Matches'),
          NavigationDestination(
              icon: Icon(Icons.leaderboard_outlined, semanticLabel: 'Standings'),
              selectedIcon: Icon(Icons.leaderboard, semanticLabel: 'Standings'),
              label: 'Standings'),
          NavigationDestination(
              icon: Icon(Icons.storefront_outlined, semanticLabel: 'Store'),
              selectedIcon: Icon(Icons.storefront, semanticLabel: 'Store'),
              label: 'Store'),
          NavigationDestination(
              icon: Icon(Icons.groups_outlined, semanticLabel: 'Club'),
              selectedIcon: Icon(Icons.groups, semanticLabel: 'Club'),
              label: 'Club'),
        ],
      ),
    );
  }
}
