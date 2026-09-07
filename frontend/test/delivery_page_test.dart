import 'dart:convert';

import 'package:erp_manufaktur/core/api_client.dart';
import 'package:erp_manufaktur/features/auth/auth_controller.dart';
import 'package:erp_manufaktur/features/delivery/delivery_page.dart';
import 'package:erp_manufaktur/features/users/user_model.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

void main() {
  testWidgets('delivery history renders one document with all batch lines', (
    tester,
  ) async {
    final auth = AuthController(
      ApiClient(client: _DeliveryClient(), baseUrl: 'http://test'),
    );
    auth.currentUser = _courier;
    auth.api.token = 'token';

    await tester.pumpWidget(MaterialApp(home: DeliveryPage(auth: auth)));
    await tester.pumpAndSettle();

    expect(find.textContaining('DLV-010926-000'), findsOneWidget);
    expect(find.textContaining('2 item(s)'), findsOneWidget);
    expect(find.textContaining('FG-001 / Lot LOT-A'), findsOneWidget);
    expect(find.textContaining('FG-002 / Lot LOT-B'), findsOneWidget);
  });
}

class _DeliveryClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final body = request.url.path.endsWith('/delivery')
        ? {
            'items': [
              {
                'delivery_number': 'DLV-010926-000',
                'delivery_date': '2026-09-01',
                'sales_order_number': 'SO-001',
                'customer_name': 'Customer A',
                'product_code': 'FG-001',
                'lot_number': 'LOT-A',
                'quantity': 2,
                'unit': 'pcs',
                'vehicle_number': null,
                'transportation_code': null,
                'driver_name': 'Driver A',
                'notes': '',
                'status': 'posted',
                'can_reverse': true,
                'created_at': '2026-09-01T00:00:00Z',
                'lines': [
                  {
                    'sales_order_item_id': 1,
                    'product_code': 'FG-001',
                    'lot_id': 1,
                    'lot_number': 'LOT-A',
                    'quantity': 2,
                    'unit': 'pcs',
                  },
                  {
                    'sales_order_item_id': 2,
                    'product_code': 'FG-002',
                    'lot_id': 2,
                    'lot_number': 'LOT-B',
                    'quantity': 3,
                    'unit': 'pcs',
                  },
                ],
              },
            ],
            'total': 1,
            'page': 1,
            'size': 100,
          }
        : <String, dynamic>{};
    return http.StreamedResponse(
      Stream.value(utf8.encode(jsonEncode(body))),
      200,
    );
  }
}

final _courier = UserModel(
  id: 'USR-001',
  firstName: 'Courier',
  lastName: 'A',
  email: 'courier@example.com',
  gender: 'male',
  role: 'courier',
  ktpNumber: '0000000000000000',
  isActive: true,
  createdAt: DateTime(2026),
  updatedAt: DateTime(2026),
  accessLevel: 'staff',
  canEdit: false,
  canDelete: false,
);
