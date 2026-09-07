import 'package:erp_manufaktur/features/receiving/receiving_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('receiving maps list, stock impact, and reversal permission', () {
    final record = ReceivingModel.fromJson({
      'receipt_number': 'RCV-140826-000',
      'receipt_date': '2026-08-14',
      'product_code': 'PRD',
      'product_name': 'Steel Plate',
      'description': 'Steel Plate SP-01',
      'lot_number': 'LOT-01',
      'quantity_grams': '1000.000',
      'unit': 'pcs',
      'plant_code': 'A1B2C',
      'plant_name': 'Main Plant',
      'storage_location_code': 'RACK',
      'storage_location_name': 'Rack A',
      'source': 'Supplier Example',
      'source_type': 'supplier',
      'source_code': 'SUP',
      'document_number': 'SJ-001',
      'po_number': 'PO-001',
      'vehicle_number': 'B 1234 CD',
      'driver_name': 'Andi',
      'notes': '',
      'receiver_name': 'Warehouse Staff',
      'status': 'posted',
      'reversal_reason': null,
      'product_stock_after_grams': '5000.000',
      'lot_stock_after_grams': '1000.000',
      'can_reverse': true,
    });

    expect(record.receiptNumber, 'RCV-140826-000');
    expect(record.quantityGrams, 1000);
    expect(record.unit, 'pcs');
    expect(record.productStockAfterGrams, 5000);
    expect(record.lotStockAfterGrams, 1000);
    expect(record.canReverse, isTrue);
    expect(receivingStatusLabel(record.status), 'Posted');
  });
}
