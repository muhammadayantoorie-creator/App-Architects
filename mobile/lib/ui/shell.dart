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

class _TenantLogo extends StatelessWidget {
  const _TenantLogo({required this.url, required this.name});
  final String? url;
  final String name;

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final fallback = CircleAvatar(
      radius: 18,
      backgroundColor: Colors.white,
      child: Text(name.isEmpty ? '?' : name[0].toUpperCase(),
          style: TextStyle(color: s.primary, fontWeight: FontWeight.w800),
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
