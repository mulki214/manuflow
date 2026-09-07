import 'package:flutter/material.dart';

import '../features/auth/auth_controller.dart';
import 'app_sidebar.dart';
import 'desktop_sidebar_shell.dart';
import 'module_navigation.dart';

/// The common frame for every top-level ERP module.
///
/// It keeps desktop and mobile navigation aligned: one sidebar implementation,
/// one application header, and Navigator history for the Back action.
class AppModuleScaffold extends StatelessWidget {
  const AppModuleScaffold({
    super.key,
    required this.auth,
    required this.activeModule,
    required this.title,
    required this.body,
    this.actions = const [],
    this.floatingActionButton,
    this.onChangePassword,
  });

  final AuthController auth;
  final AppModule activeModule;
  final String title;
  final Widget body;
  final List<Widget> actions;
  final Widget? floatingActionButton;
  final VoidCallback? onChangePassword;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) => DesktopSidebarShell(
      auth: auth,
      activeModule: activeModule,
      onModuleSelected: (module) =>
          navigateToModule(context, auth, module, activeModule: activeModule),
      child: Scaffold(
        appBar: AppBar(title: Text(title), actions: actions),
        // A mobile Drawer must not be available beside the permanent desktop sidebar.
        drawer: constraints.maxWidth >= 1000
            ? null
            : Drawer(
                child: SafeArea(
                  child: AppSidebar(
                    auth: auth,
                    activeModule: activeModule,
                    onModuleSelected: (module) {
                      Navigator.of(context).pop();
                      navigateToModule(
                        context,
                        auth,
                        module,
                        activeModule: activeModule,
                      );
                    },
                    onChangePassword: onChangePassword,
                  ),
                ),
              ),
        body: body,
        floatingActionButton: floatingActionButton,
      ),
    ),
  );
}
