import 'package:flutter/material.dart';

ThemeData buildTheme(Color seed, Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: seed, brightness: brightness);
  final radius = BorderRadius.circular(12);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: 'Roboto',
    scaffoldBackgroundColor: scheme.surface,
    cardTheme: CardThemeData(
      elevation: 0,
      margin: EdgeInsets.zero,
      color: scheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: BorderSide(color: scheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(minimumSize: const Size(64, 48)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(minimumSize: const Size(64, 48)),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
    ),
    inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
  );
}

/// Fixed accent for "clinched" rows (always paired with a text label).
const clinchedColor = Color(0xFF2E7D32);
