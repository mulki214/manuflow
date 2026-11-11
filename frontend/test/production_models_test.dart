import 'package:erp_manufaktur/features/production/production_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('production process maps ownership and availability fields', () {
    final process = ProductionProcessModel.fromJson({
      'code': 'OP-CUT',
      'name': 'Cutting',
      'description': 'Cut raw material',
      'process_type': 'production',
      'plant_code': 'PL001',
      'plant_name': 'Main Plant',
      'is_active': true,
      'can_delete': false,
    });

    expect(process.code, 'OP-CUT');
    expect(process.type, 'production');
    expect(process.plantName, 'Main Plant');
    expect(process.isActive, isTrue);
    expect(process.canDelete, isFalse);
  });

  test('WIP job maps the warehouse-created lot segment and queue state', () {
    final job = ProductionWipJobModel.fromJson({
      'id': 4,
      'source_transfer_number': 'SM-190826-000',
      'process_code': 'OP1',
      'process_name': 'Cutting',
      'process_type': 'production',
      'product_code': 'PRD01',
      'product_name': 'Part',
      'description': 'Part 01',
      'lot_number': 'LOT-01',
      'lot_segment_code': 'LOT-01-SM-190826-000',
      'plant_code': 'PL001',
      'plant_name': 'Main Plant',
      'unit': 'pcs',
      'input_quantity': '100',
      'current_quantity': '75.5',
      'status': 'queued',
      'can_complete': true,
    });

    expect(job.segmentCode, 'LOT-01-SM-190826-000');
    expect(job.currentQuantity, 75.5);
    expect(job.canComplete, isTrue);
  });

  test('inter-plant transfer maps the dispatch and receipt audit fields', () {
    final transfer = InterPlantWipTransferModel.fromJson({
      'id': 12,
      'transfer_number': 'IPW-111126-0012',
      'transfer_date': '2026-11-11',
      'source_job_id': 4,
      'received_job_id': null,
      'product_code': 'PRD01',
      'product_name': 'Part',
      'description': 'Part 01',
      'lot_number': 'LOT-01',
      'lot_segment_code': 'LOT-01-SM-190826-000',
      'unit': 'pcs',
      'quantity': '25',
      'source_plant_code': 'PL001',
      'source_plant_name': 'Source Plant',
      'source_process_code': 'OP1',
      'source_process_name': 'Cutting',
      'destination_plant_code': 'PL002',
      'destination_plant_name': 'Destination Plant',
      'destination_process_code': 'OP2',
      'destination_process_name': 'Finishing',
      'status': 'in_transit',
      'notes': '',
      'dispatched_by': '000000001',
      'dispatched_by_name': 'Operator One',
      'dispatched_at': '2026-11-11T08:00:00Z',
      'received_by': null,
      'received_by_name': null,
      'received_at': null,
      'can_receive': true,
    });

    expect(transfer.number, 'IPW-111126-0012');
    expect(transfer.quantity, 25);
    expect(transfer.destinationPlantName, 'Destination Plant');
    expect(transfer.status, 'in_transit');
    expect(transfer.canReceive, isTrue);
  });
}
