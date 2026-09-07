import 'package:flutter/material.dart';

import 'features/auth/auth_controller.dart';
import 'features/auth/login_page.dart';
import 'features/users/user_page.dart';

class ErpApp extends StatelessWidget {
  const ErpApp({super.key, required this.auth});

  final AuthController auth;

  @override
  Widget build(BuildContext context) {
    const primary = Color(0xFF155EEF);
    return MaterialApp(
      title: 'Manuflow ERP',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: primary,
          brightness: Brightness.light,
          surface: const Color(0xFFF7F8FA),
        ),
        scaffoldBackgroundColor: const Color(0xFFF7F8FA),
        inputDecorationTheme: const InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: Color(0xFFD0D5DD)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: Color(0xFFD0D5DD)),
          ),
        ),
        cardTheme: const CardThemeData(
          color: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(16)),
            side: BorderSide(color: Color(0xFFEAECF0)),
          ),
        ),
      ),
      home: ListenableBuilder(
        listenable: auth,
        builder: (context, _) =>
            auth.isAuthenticated ? UserPage(auth: auth) : LoginPage(auth: auth),
      ),
    );
  }
}
