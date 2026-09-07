import 'package:flutter_test/flutter_test.dart';
import 'package:erp_manufaktur/app.dart';
import 'package:erp_manufaktur/core/api_client.dart';
import 'package:erp_manufaktur/features/auth/auth_controller.dart';

void main() {
  testWidgets('menampilkan form login', (WidgetTester tester) async {
    await tester.pumpWidget(
      ErpApp(auth: AuthController(ApiClient(baseUrl: 'http://localhost'))),
    );

    expect(find.text('MANUFLOW'), findsOneWidget);
    expect(find.text('Selamat datang'), findsOneWidget);
    expect(find.text('Email'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Masuk'), findsOneWidget);
  });
}
