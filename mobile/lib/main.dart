import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/nav.dart';
import 'core/theme.dart';
import 'data/app_state.dart';
import 'data/cart.dart';
import 'ui/screens/login.dart';
import 'ui/shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState();
  try {
    await state.init();
  } catch (e, st) {
    // Never block the first frame: the app still opens (sign-in) if local setup fails.
    debugPrint('init failed: $e\n$st');
  }
  runApp(MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: state),
      ChangeNotifierProvider(create: (_) => Cart()),
    ],
    child: const NasconApp(),
  ));
}

class NasconApp extends StatelessWidget {
  const NasconApp({super.key});

  @override
  Widget build(BuildContext context) {
    final seed = context.select<AppState, Color>((s) => s.seed);
    final loggedIn = context.select<AppState, bool>((s) => s.loggedIn);
    return MaterialApp(
      title: 'Huddle',
      debugShowCheckedModeBanner: false,
      navigatorKey: navKey,
      scaffoldMessengerKey: messengerKey,
      theme: buildTheme(seed, Brightness.light),
      darkTheme: buildTheme(seed, Brightness.dark),
      themeMode: ThemeMode.light,
      home: loggedIn ? const Shell() : const LoginScreen(),
    );
  }
}
