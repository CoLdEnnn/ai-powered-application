import 'package:flutter/material.dart';

import 'screens/welcome.dart';
import 'shell.dart';
import 'state.dart';
import 'ui.dart';

void main() => runApp(const AituApp());

class AituApp extends StatelessWidget {
  const AituApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AITU Assistant',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: false,
        colorScheme: const ColorScheme.light(primary: kPrimary),
        scaffoldBackgroundColor: kBg,
        dividerColor: kBorder,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: kText,
          elevation: 0,
        ),
      ),
      home: ListenableBuilder(
        listenable: app,
        builder: (context, _) => app.started ? const AppShell() : const WelcomeScreen(),
      ),
    );
  }
}
