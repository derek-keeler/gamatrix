// Main application entry point for Flutter Gamatrix

import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const FlutterGamatrixApp());
}

class FlutterGamatrixApp extends StatelessWidget {
  const FlutterGamatrixApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Gamatrix',
      theme: ThemeData(
        // Dark theme to match the original web UI
        brightness: Brightness.dark,
        primarySwatch: Colors.teal,
        scaffoldBackgroundColor: const Color(0xFF323232), // rgb(50, 50, 50)
        textTheme: const TextTheme(
          bodyLarge: TextStyle(color: Colors.grey, fontSize: 18),
          bodyMedium: TextStyle(color: Colors.grey, fontSize: 16),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF323232),
          foregroundColor: Colors.grey,
          elevation: 0,
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF424242),
          elevation: 4,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
        checkboxTheme: CheckboxThemeData(
          fillColor: WidgetStateProperty.resolveWith<Color?>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.selected)) {
                return Colors.teal;
              }
              return null;
            },
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.teal,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            textStyle: const TextStyle(fontSize: 18),
          ),
        ),
      ),
      home: const HomeScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}