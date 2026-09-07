import 'package:flutter/material.dart';

import '../features/auth/auth_controller.dart';
import 'app_sidebar.dart';

class DesktopSidebarShell extends StatelessWidget {
  const DesktopSidebarShell({
    super.key,
    required this.auth,
    required this.activeModule,
    required this.onModuleSelected,
    required this.child,
  });

  final AuthController auth;
  final AppModule activeModule;
  final ValueChanged<AppModule> onModuleSelected;
  final Widget child;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      if (constraints.maxWidth < 1000) return child;
      return Scaffold(
        body: Row(
          children: [
            AppSidebar(
              auth: auth,
              activeModule: activeModule,
              onModuleSelected: onModuleSelected,
            ),
            Expanded(child: child),
          ],
        ),
      );
    },
  );
}
