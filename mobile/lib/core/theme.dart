import 'package:flutter/material.dart';

/// Huddle palette: black + lime sports style.
class AppColors {
  static const primary = Color(0xFFB8F400); // lime
  static const primaryDark = Color(0xFF8FBF00);
  static const onPrimary = Color(0xFF0B0B0B);
  static const header = Color(0xFF1C1C1E); // dark header blocks / cards
  static const accent = Color(0xFFB8F400);
  static const live = Color(0xFFFF3B30);
  static const bg = Color(0xFF0B0B0B);
  static const card = Color(0xFF1C1C1E);
  static const chip = Color(0xFF2C2C2E);
  static const textMain = Color(0xFFFFFFFF);
  static const textSub = Color(0xFFA0A0A5);
  static const divider = Color(0xFF2C2C2E);
  static const rowAlt = Color(0xFF151517);
  static const qualifyBar = Color(0xFFB8F400);
  static const eliminatedBar = Color(0xFFFF3B30);
}

ThemeData buildTheme(Color tenantSeed, Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: AppColors.primary, brightness: Brightness.dark).copyWith(
    primary: AppColors.primary,
    onPrimary: AppColors.onPrimary,
    primaryContainer: AppColors.chip,
    onPrimaryContainer: AppColors.primary,
    secondaryContainer: AppColors.chip,
    onSecondaryContainer: Colors.white,
    surface: AppColors.bg,
    onSurface: AppColors.textMain,
    onSurfaceVariant: AppColors.textSub,
    surfaceContainerLow: AppColors.card,
    surfaceContainer: AppColors.card,
    outline: const Color(0xFF48484A),
    outlineVariant: AppColors.divider,
    tertiary: tenantSeed,
  );
  final r = BorderRadius.circular(28);
  const text = TextTheme(
    headlineSmall: TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: AppColors.textMain),
    titleLarge: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: AppColors.textMain),
    titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textMain),
    titleSmall: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.textMain),
    bodyLarge: TextStyle(fontSize: 15, color: AppColors.textMain),
    bodyMedium: TextStyle(fontSize: 14, color: AppColors.textMain),
    bodySmall: TextStyle(fontSize: 12, color: AppColors.textSub),
    labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
    labelSmall: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.8),
  );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    fontFamily: 'Roboto',
    textTheme: text,
    scaffoldBackgroundColor: AppColors.bg,
    dividerColor: AppColors.divider,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.bg,
      foregroundColor: Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle:
          TextStyle(fontFamily: 'Roboto', fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white),
      iconTheme: IconThemeData(color: Colors.white),
      actionsIconTheme: IconThemeData(color: Colors.white),
    ),
    cardTheme: CardThemeData(
      color: AppColors.card,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      clipBehavior: Clip.antiAlias,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.card,
      indicatorColor: AppColors.primary,
      indicatorShape: const StadiumBorder(),
      height: 68,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      iconTheme: WidgetStateProperty.resolveWith((s) => IconThemeData(
          color: s.contains(WidgetState.selected) ? AppColors.onPrimary : AppColors.textSub)),
      labelTextStyle: WidgetStateProperty.resolveWith((s) => TextStyle(
          fontSize: 12,
          fontWeight: s.contains(WidgetState.selected) ? FontWeight.w800 : FontWeight.w500,
          color: s.contains(WidgetState.selected) ? AppColors.primary : AppColors.textSub)),
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: AppColors.primary,
      unselectedLabelColor: AppColors.textSub,
      indicatorColor: AppColors.primary,
      indicatorSize: TabBarIndicatorSize.label,
      dividerColor: AppColors.divider,
      labelStyle: TextStyle(fontWeight: FontWeight.w800),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.onPrimary,
        disabledBackgroundColor: AppColors.chip,
        minimumSize: const Size(64, 52),
        shape: RoundedRectangleBorder(borderRadius: r),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: AppColors.onPrimary,
        minimumSize: const Size(64, 52),
        shape: RoundedRectangleBorder(borderRadius: r),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        backgroundColor: AppColors.chip,
        minimumSize: const Size(64, 48),
        side: BorderSide.none,
        shape: RoundedRectangleBorder(borderRadius: r),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48), foregroundColor: AppColors.primary),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.card,
      labelStyle: const TextStyle(color: AppColors.textSub),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
      enabledBorder:
          OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: AppColors.primary, width: 2)),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: AppColors.chip,
      selectedColor: AppColors.primary,
      checkmarkColor: AppColors.onPrimary,
      side: BorderSide.none,
      shape: const StadiumBorder(),
      labelStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(color: AppColors.onPrimary, fontWeight: FontWeight.w800),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? AppColors.primary : AppColors.chip),
        foregroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? AppColors.onPrimary : Colors.white),
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: AppColors.primary,
      foregroundColor: AppColors.onPrimary,
      shape: StadiumBorder(),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.primary),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.chip,
      contentTextStyle: TextStyle(color: Colors.white),
    ),
  );
}

const clinchedColor = AppColors.qualifyBar;
