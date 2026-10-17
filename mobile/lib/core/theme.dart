import 'package:flutter/material.dart';

/// Huddle palette (sports-app style: green header, white cards, dense layout).
class AppColors {
  static const primary = Color(0xFFD84315);
  static const primaryDark = Color(0xFFBF360C);
  static const accent = Color(0xFFFFC107);
  static const live = Color(0xFFE53935);
  static const bg = Color(0xFFF4F2F1);
  static const card = Color(0xFFFFFFFF);
  static const textMain = Color(0xFF1A1A1A);
  static const textSub = Color(0xFF6B6B6B);
  static const divider = Color(0xFFE3E7E5);
  static const rowAlt = Color(0xFFFBF7F5);
  static const qualifyBar = Color(0xFF2E7D32);
  static const eliminatedBar = Color(0xFFE53935);
}

/// The app chrome is always Huddle green; the tenant colour is only used for small accents.
ThemeData buildTheme(Color tenantSeed, Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: AppColors.primary).copyWith(
    primary: AppColors.primary,
    onPrimary: Colors.white,
    surface: AppColors.card,
    onSurface: AppColors.textMain,
    onSurfaceVariant: AppColors.textSub,
    outlineVariant: AppColors.divider,
    tertiary: tenantSeed,
  );
  final r8 = BorderRadius.circular(8);
  const text = TextTheme(
    titleLarge: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppColors.textMain),
    titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textMain),
    titleSmall: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.textMain),
    bodyLarge: TextStyle(fontSize: 15, color: AppColors.textMain),
    bodyMedium: TextStyle(fontSize: 14, color: AppColors.textMain),
    bodySmall: TextStyle(fontSize: 12, color: AppColors.textSub),
    labelSmall: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: 'Roboto',
    textTheme: text,
    scaffoldBackgroundColor: AppColors.bg,
    dividerColor: AppColors.divider,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.primary,
      foregroundColor: Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle:
          TextStyle(fontFamily: 'Roboto', fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
      iconTheme: IconThemeData(color: Colors.white),
      actionsIconTheme: IconThemeData(color: Colors.white),
    ),
    cardTheme: CardThemeData(
      color: AppColors.card,
      elevation: 1,
      margin: EdgeInsets.zero,
      shadowColor: Colors.black26,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      clipBehavior: Clip.antiAlias,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      indicatorColor: AppColors.primary.withValues(alpha: 0.12),
      height: 64,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      iconTheme: WidgetStateProperty.resolveWith((s) => IconThemeData(
          color: s.contains(WidgetState.selected) ? AppColors.primary : AppColors.textSub)),
      labelTextStyle: WidgetStateProperty.resolveWith((s) => TextStyle(
          fontSize: 12,
          fontWeight: s.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: s.contains(WidgetState.selected) ? AppColors.primary : AppColors.textSub)),
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: AppColors.primary,
      unselectedLabelColor: AppColors.textSub,
      indicatorColor: AppColors.primary,
      indicatorSize: TabBarIndicatorSize.tab,
      labelStyle: TextStyle(fontWeight: FontWeight.w700),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        minimumSize: const Size(64, 48),
        shape: RoundedRectangleBorder(borderRadius: r8),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        minimumSize: const Size(64, 48),
        shape: RoundedRectangleBorder(borderRadius: r8),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.primary,
        minimumSize: const Size(64, 48),
        side: const BorderSide(color: AppColors.primary, width: 1.5),
        shape: RoundedRectangleBorder(borderRadius: r8),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48), foregroundColor: AppColors.primary),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(borderRadius: r8),
      enabledBorder: OutlineInputBorder(
          borderRadius: r8, borderSide: const BorderSide(color: AppColors.divider)),
      focusedBorder: OutlineInputBorder(
          borderRadius: r8, borderSide: const BorderSide(color: AppColors.primary, width: 2)),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Colors.white,
      selectedColor: AppColors.primary,
      checkmarkColor: Colors.white,
      side: const BorderSide(color: AppColors.divider),
      labelStyle: const TextStyle(color: AppColors.textMain, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? AppColors.primary : Colors.white),
        foregroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? Colors.white : AppColors.textMain),
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: AppColors.primary,
      foregroundColor: Colors.white,
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: Color(0xFF263238),
      contentTextStyle: TextStyle(color: Colors.white),
    ),
  );
}

/// Accent for "clinched" rows (always paired with a text label).
const clinchedColor = AppColors.qualifyBar;
