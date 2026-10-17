import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/config.dart';
import '../../core/nav.dart';
import '../../core/theme.dart';
import '../../data/app_state.dart';
import 'settings.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _obscure = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_email.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Enter your email and password.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final s = context.read<AppState>();
    try {
      await s.login(_email.text, _password.text);
      showSnack('Signed in as ${roleLabel(s.role)}.');
    } on ApiException catch (e) {
      setState(() => _error = e.isNetwork
          ? "Couldn't reach the server. Check the server address (gear icon) and your connection."
          : e.status == 401 || e.status == 400 || e.code == 'VALIDATION_ERROR'
              ? 'Email or password is incorrect.'
              : e.message);
    } catch (_) {
      setState(() => _error = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _quick(String email) {
    _email.text = email;
    _password.text = demoPassword;
    _submit();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sign in'),
        actions: [
          IconButton(
            tooltip: 'Server settings',
            icon: const Icon(Icons.settings, semanticLabel: 'Server settings'),
            onPressed: () => Navigator.push(
                context, MaterialPageRoute<void>(builder: (_) => const SettingsScreen())),
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: AutofillGroup(
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: AppColors.primary,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Row(children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: Image.asset('assets/icon.png',
                            width: 64, height: 64, semanticLabel: 'Huddle logo'),
                      ),
                      const SizedBox(width: 16),
                      const Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('Huddle',
                              style: TextStyle(
                                  color: Colors.white, fontSize: 34, fontWeight: FontWeight.w800)),
                          Text('Leagues · Clubs · Store',
                              style: TextStyle(color: Colors.white70, fontSize: 14)),
                        ]),
                      ),
                    ]),
                  ),
                  const SizedBox(height: 24),
                  if (s.sessionMessage != null) ...[
                    _Notice(text: s.sessionMessage!),
                    const SizedBox(height: 16),
                  ],
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                        labelText: 'Email', prefixIcon: Icon(Icons.mail_outline)),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _password,
                    obscureText: _obscure,
                    autofillHints: const [AutofillHints.password],
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: 'Password',
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(
                        tooltip: _obscure ? 'Show password' : 'Hide password',
                        icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off,
                            semanticLabel: _obscure ? 'Show password' : 'Hide password'),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    _Notice(text: _error!),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    child: _busy
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                                strokeWidth: 2.5, semanticsLabel: 'Signing in'))
                        : const Text('Sign in'),
                  ),
                  const SizedBox(height: 24),
                  Text('Quick login (demo accounts)', style: t.textTheme.titleSmall),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    for (final (label, email) in demoAccounts)
                      ActionChip(
                        avatar: const Icon(Icons.person_outline, size: 18),
                        label: Text(label),
                        tooltip: 'Sign in as $email',
                        onPressed: _busy ? null : () => _quick(email),
                      ),
                  ]),
                  const SizedBox(height: 24),
                  Text(s.demo ? 'Demo data mode — no server needed' : 'Server: ${s.api.baseUrl}',
                      style: t.textTheme.bodySmall
                          ?.copyWith(color: t.colorScheme.onSurfaceVariant)),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
            color: s.errorContainer, borderRadius: BorderRadius.circular(12)),
        child: Row(children: [
          Icon(Icons.error_outline, color: s.onErrorContainer, semanticLabel: 'Error'),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: TextStyle(color: s.onErrorContainer))),
        ]),
      ),
    );
  }
}
