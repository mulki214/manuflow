import 'package:erp_manufaktur/features/master_data/master_data_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('product record maps part name and part number summary', () {
    final record = MasterDataRecord(MasterDataType.product, {
      'code': 'BP001',
      'part_name': 'Brake Pad',
      'part_no': 'B-100',
      'customer_name': 'Customer A',
      'supplier_name': 'Supplier B',
      'stock_by_unit': {'pcs': '1250.500', 'pail': '5.000'},
    });

    expect(record.code, 'BP001');
    expect(record.name, 'Brake Pad');
    expect(record.subtitle, 'Customer A • Supplier B');
    expect(record.stockLabel, '1250.5 pcs • 5 pail');
  });

  test('corporation record derives combined business type', () {
    final record = MasterDataRecord(MasterDataType.corporation, {
      'code': 'PAM',
      'name': 'PT Astra Motor',
      'is_customer': true,
      'is_supplier': true,
    });

    expect(record.subtitle, '-');
  });
}
