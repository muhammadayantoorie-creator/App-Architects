import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/config.dart';
import '../../core/nav.dart';
import '../../core/theme.dart';
import '../../data/app_state.dart';
import '../widgets/sports.dart';
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
    OutlineInputBorder pill(Color c, [double w = 1]) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(30), borderSide: BorderSide(color: c, width: w));
    InputDecoration field(String label, IconData icon, {Widget? suffix}) => InputDecoration(
          labelText: label,
          prefixIcon: Padding(
              padding: const EdgeInsets.only(left: 8), child: Icon(icon, color: AppColors.textSub)),
          suffixIcon: suffix,
          filled: true,
          fillColor: AppColors.card,
          contentPadding: const EdgeInsets.symmetric(horizontal: 22, vertical: 20),
          border: pill(AppColors.chip),
          enabledBorder: pill(AppColors.chip),
          focusedBorder: pill(AppColors.primary, 2),
        );
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SingleChildScrollView(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(
            height: 350,
            decoration: const BoxDecoration(
              color: AppColors.header,
              image: DecorationImage(image: AssetImage('assets/stadium.jpg'), fit: BoxFit.cover),
            ),
            child: Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0x99000000), Color(0x33000000), AppColors.bg],
                ),
              ),
              child: SafeArea(
                bottom: false,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 12, 16, 12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      ClipOval(
                        child: Image.asset('assets/icon.png',
                            width: 52, height: 52, semanticLabel: 'Huddle logo'),
                      ),
                      const Spacer(),
                      Material(
                        color: const Color(0xCC2C2C2E),
                        shape: const CircleBorder(),
                        child: IconButton(
                          tooltip: 'Server settings',
                          icon: const Icon(Icons.settings_outlined,
                              color: Colors.white, semanticLabel: 'Server settings'),
                          onPressed: () => Navigator.push(context,
                              MaterialPageRoute<void>(builder: (_) => const SettingsScreen())),
                        ),
                      ),
                    ]),
                    const Spacer(),
                    const Text('Welcome to',
                        style: TextStyle(
                            color: Color(0xFFD0D0D5),
                            fontSize: 30,
                            fontWeight: FontWeight.w300,
                            height: 1.1)),
                    const FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text('HUDDLE',
                          style: TextStyle(
                              fontFamily: condensedFont,
                              color: Colors.white,
                              fontSize: 84,
                              fontWeight: FontWeight.w900,
                              height: 1.0,
                              letterSpacing: -2)),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                          color: AppColors.primary, borderRadius: BorderRadius.circular(20)),
                      child: const Text('Leagues · Clubs · Store',
                          style: TextStyle(
                              color: AppColors.onPrimary, fontSize: 13, fontWeight: FontWeight.w800)),
                    ),
                  ]),
                ),
              ),
            ),
          ),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
                child: AutofillGroup(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    if (s.sessionMessage != null) ...[
                      _Notice(text: s.sessionMessage!),
                      const SizedBox(height: 16),
                    ],
                    TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      textInputAction: TextInputAction.next,
                      decoration: field('Email', Icons.mail_outline),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _password,
                      obscureText: _obscure,
                      autofillHints: const [AutofillHints.password],
                      textInputAction: TextInputAction.done,
                      onSubmitted: (_) => _submit(),
                      decoration: field(
                        'Password',
                        Icons.lock_outline,
                        suffix: Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: IconButton(
                            tooltip: _obscure ? 'Show password' : 'Hide password',
                            icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off,
                                color: AppColors.textSub,
                                semanticLabel: _obscure ? 'Show password' : 'Hide password'),
                            onPressed: () => setState(() => _obscure = !_obscure),
                          ),
                        ),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      _Notice(text: _error!),
                    ],
                    const SizedBox(height: 24),
                    SizedBox(
                      height: 58,
                      child: FilledButton(
                        onPressed: _busy ? null : _submit,
                        child: _busy
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2.5, semanticsLabel: 'Signing in'))
                            : const Text('SIGN IN',
                                style: TextStyle(
                                    fontFamily: condensedFont,
                                    fontSize: 20,
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: 1)),
                      ),
                    ),
                    const SizedBox(height: 36),
                    const Text('QUICK LOGIN',
                        style: TextStyle(
                            color: AppColors.textSub,
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.5)),
                    const SizedBox(height: 12),
                    Wrap(spacing: 10, runSpacing: 10, children: [
                      for (final (label, email) in demoAccounts)
                        ActionChip(
                          avatar: const Icon(Icons.person_outline, size: 18, color: AppColors.primary),
                          label: Text(label,
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                          tooltip: 'Sign in as $email',
                          shape: const StadiumBorder(),
                          side: BorderSide.none,
                          backgroundColor: AppColors.chip,
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 10),
                          onPressed: _busy ? null : () => _quick(email),
                        ),
                    ]),
                    const SizedBox(height: 28),
                    Text(s.demo ? 'Demo data mode — no server needed' : 'Server: ${s.api.baseUrl}',
                        style: const TextStyle(color: AppColors.textSub, fontSize: 12)),
                  ]),
                ),
              ),
            ),
          ),
        ]),
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
