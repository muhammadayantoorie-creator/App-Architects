import 'package:flutter/material.dart';

/// Sports-app look (FotMob / OneFootball style): bold team-colour app bar, vivid accents,
/// bright surfaces, strong typography for scores.
ThemeData buildTheme(Color seed, Brightness brightness) {
  final scheme = ColorScheme.fromSeed(
    seedColor: seed,
    brightness: brightness,
    dynamicSchemeVariant: DynamicSchemeVariant.fidelity,
  );
  final radius = BorderRadius.circular(12);
  final dark = brightness == Brightness.dark;
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: 'Roboto',
    scaffoldBackgroundColor: dark ? scheme.surface : const Color(0xFFF2F4F7),
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.primary,
      foregroundColor: scheme.onPrimary,
      elevation: 2,
      scrolledUnderElevation: 4,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: 'Roboto',
        fontSize: 20,
        fontWeight: FontWeight.w800,
        color: scheme.onPrimary,
        letterSpacing: 0.2,
      ),
      iconTheme: IconThemeData(color: scheme.onPrimary),
      actionsIconTheme: IconThemeData(color: scheme.onPrimary),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: dark ? scheme.surfaceContainer : Colors.white,
      indicatorColor: scheme.primary,
      elevation: 8,
      iconTheme: WidgetStateProperty.resolveWith((s) => IconThemeData(
            color: s.contains(WidgetState.selected) ? scheme.onPrimary : scheme.onSurfaceVariant,
          )),
      labelTextStyle: WidgetStateProperty.resolveWith((s) => TextStyle(
            fontWeight: s.contains(WidgetState.selected) ? FontWeight.w800 : FontWeight.w500,
            color: s.contains(WidgetState.selected) ? scheme.primary : scheme.onSurfaceVariant,
          )),
    ),
    tabBarTheme: TabBarThemeData(
      labelColor: scheme.primary,
      unselectedLabelColor: scheme.onSurfaceVariant,
      indicatorColor: scheme.primary,
      labelStyle: const TextStyle(fontWeight: FontWeight.w800),
    ),
    cardTheme: CardThemeData(
      elevation: dark ? 0 : 1.5,
      margin: EdgeInsets.zero,
      color: dark ? scheme.surfaceContainerLow : Colors.white,
      shadowColor: Colors.black26,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: dark ? BorderSide(color: scheme.outlineVariant) : BorderSide.none,
      ),
      clipBehavior: Clip.antiAlias,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 48),
        textStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(64, 48),
        foregroundColor: scheme.primary,
        side: BorderSide(color: scheme.primary, width: 1.5),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
    ),
    chipTheme: ChipThemeData(
      selectedColor: scheme.primary,
      labelStyle: const TextStyle(fontWeight: FontWeight.w600),
      secondaryLabelStyle: TextStyle(color: scheme.onPrimary, fontWeight: FontWeight.w700),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: scheme.tertiary,
      foregroundColor: scheme.onTertiary,
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: const OutlineInputBorder(),
      filled: !dark,
      fillColor: Colors.white,
    ),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
  );
}

/// Fixed accent for "clinched" rows (always paired with a text label).
const clinchedColor = Color(0xFF2E7D32);
