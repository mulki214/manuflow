import 'package:erp_manufaktur/shared/mobile_product_scanner.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('scanned product identity maps product and optional lot', () {
    final item = ScannedProductIdentity.fromJson({
      'product_code': 'PJA',
      'product_name': 'Produk Jadi ABC',
      'description': 'Produk Jadi ABC 789',
      'lot_id': 11,
      'lot_number': 'LOT-11',
      'unit': 'pcs',
      'available_quantity': '100',
    });

    expect(item.key, 'PJA:11');
    expect(item.lotNumber, 'LOT-11');
    expect(item.availableQuantity, 100);
  });
}
