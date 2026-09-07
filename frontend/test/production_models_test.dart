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
}
