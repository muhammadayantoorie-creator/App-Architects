import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// Shown while the app starts (local database, secure token, connectivity) before sign-in/home.
class SplashApp extends StatelessWidget {
  const SplashApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Huddle',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(AppColors.primary, Brightness.dark),
        home: const SplashScreen(),
      );
}

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        child: Center(
          child: Semantics(
            label: 'Loading Huddle',
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(28),
                child: Image.asset('assets/icon.png', width: 112, height: 112),
              ),
              const SizedBox(height: 24),
              const Text('HUDDLE',
                  style: TextStyle(
                      color: Colors.white, fontSize: 44, fontWeight: FontWeight.w900, letterSpacing: 2)),
              const SizedBox(height: 4),
              const Text('Leagues · Clubs · Store',
                  style: TextStyle(color: AppColors.primary, fontSize: 14, fontWeight: FontWeight.w700)),
              const SizedBox(height: 32),
              SizedBox(
                width: 160,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: const LinearProgressIndicator(
                    minHeight: 6,
                    color: AppColors.primary,
                    backgroundColor: AppColors.chip,
                  ),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
