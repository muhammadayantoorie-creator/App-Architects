import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config.dart';
import '../../core/nav.dart';
import '../../data/app_state.dart';
import '../widgets/common.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final _url = TextEditingController(text: context.read<AppState>().api.baseUrl);
  bool _testing = false;
  (bool, String)? _result;

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  String? _validate(String v) {
    final u = Uri.tryParse(v.trim());
    if (u == null || !(u.scheme == 'http' || u.scheme == 'https') || u.host.isEmpty) {
      return 'Enter an address like http://192.168.43.10:8080';
    }
    return null;
  }

  Future<void> _save() async {
    final err = _validate(_url.text);
    if (err != null) {
      setState(() => _result = (false, err));
      return;
    }
    await context.read<AppState>().setServerUrl(_url.text);
    showSnack('Server address saved.');
  }

  Future<void> _test() async {
    final err = _validate(_url.text);
    if (err != null) {
      setState(() => _result = (false, err));
      return;
    }
    setState(() {
      _testing = true;
      _result = null;
    });
    final base = _url.text.trim().replaceAll(RegExp(r'/+$'), '');
    try {
      final res = await Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 3),
        receiveTimeout: const Duration(seconds: 5),
      )).get<dynamic>('$base/health');
      final ok = (res.statusCode ?? 0) < 400;
      setState(() => _result = ok
          ? (true, 'Connected')
          : (false, 'The server answered but reported a problem. Try again shortly.'));
    } on DioException catch (e) {
      setState(() => _result = (
            false,
            e.response == null
                ? "Couldn't reach the server. Check the address and that this phone is on the same Wi-Fi or hotspot."
                : 'The server answered but reported a problem. Try again shortly.'
          ));
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Text('Server', style: t.textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Server URL',
              helperText: 'Emulator: http://10.0.2.2:8080 · Phone: http://<laptop IP>:8080',
              helperMaxLines: 2,
              prefixIcon: Icon(Icons.dns_outlined),
            ),
          ),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _testing ? null : _test,
                icon: _testing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, semanticsLabel: 'Testing connection'))
                    : const Icon(Icons.wifi_tethering, semanticLabel: 'Test connection'),
                label: const Text('Test connection'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: FilledButton.icon(
                onPressed: _save,
                icon: const Icon(Icons.save_outlined, semanticLabel: 'Save'),
                label: const Text('Save'),
              ),
            ),
          ]),
          if (_result != null) ...[
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              child: Row(children: [
                Icon(_result!.$1 ? Icons.check_circle : Icons.error_outline,
                    color: _result!.$1 ? t.colorScheme.primary : t.colorScheme.error,
                    semanticLabel: _result!.$1 ? 'Success' : 'Error'),
                const SizedBox(width: 8),
                Expanded(child: Text(_result!.$2)),
              ]),
            ),
          ],
          const Divider(height: 32),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.info_outline, semanticLabel: 'App version'),
            title: const Text('App version'),
            subtitle: const Text(appVersion),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.phone_android, semanticLabel: 'Device ID'),
            title: const Text('Device ID'),
            subtitle: Text(s.deviceId),
          ),
          if (s.loggedIn) ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.person_outline, semanticLabel: 'Signed in as'),
              title: Text('${s.me?['email'] ?? ''}'),
              subtitle: Text('Role: ${roleLabel(s.role)}'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () => confirmSignOut(context),
              icon: const Icon(Icons.logout, semanticLabel: 'Sign out'),
              label: const Text('Sign out'),
            ),
          ],
        ]),
      ),
    );
  }
}

String roleLabel(String role) => switch (role) {
      'super_admin' => 'Super admin',
      'league_organizer' => 'League organizer',
      'club_manager' => 'Club manager',
      'player' => 'Player',
      _ => 'Viewer',
    };

Future<void> confirmSignOut(BuildContext context) async {
  final s = context.read<AppState>();
  final ok = await confirmDialog(context,
      title: 'Sign out?',
      message: s.pending > 0
          ? 'You have ${s.pending} unsynced actions. They stay on this phone and sync after the next sign-in.'
          : 'You will need to sign in again to use the app.',
      confirmLabel: 'Sign out');
  if (ok) await s.logout();
}
