import 'package:erp_manufaktur/features/warehouse/warehouse_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('warehouse transfer maps WIP destination and partial quantity', () {
    final transfer = WarehouseTransferModel.fromJson({
      'transfer_number': 'SM-190826-000',
      'transfer_date': '2026-08-19',
      'product_code': 'PRD01',
      'product_name': 'Part',
      'description': 'Part 01',
      'lot_number': 'LOT-01',
      'quantity': '15.500',
      'unit': 'pcs',
      'plant_name': 'Delta',
      'source_storage_name': 'Raw Material',
      'source_location_name': 'Rack A',
      'destination_type': 'wip',
      'destination_process_code': 'CUT',
      'destination_process_name': 'Cutting',
      'document_number': 'DOC-01',
      'notes': '',
      'status': 'posted',
      'performed_by_name': 'Warehouse Staff',
      'wip_lot_segment_code': 'LOT-01-SM-190826-000',
      'wip_status': 'queued',
      'can_reverse': true,
    });

    expect(transfer.quantity, 15.5);
    expect(transfer.source, 'Raw Material — Rack A');
    expect(transfer.destination, 'CUT — Cutting');
    expect(transfer.wipStatus, 'queued');
    expect(transfer.canReverse, isTrue);
  });
}
