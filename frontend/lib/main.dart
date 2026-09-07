import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api_client.dart';
import 'features/auth/auth_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final auth = AuthController(ApiClient());
  await auth.restoreSession();
  runApp(ErpApp(auth: auth));
}
