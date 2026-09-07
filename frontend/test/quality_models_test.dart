import 'package:flutter_test/flutter_test.dart';
import 'package:erp_manufaktur/features/quality/quality_models.dart';

void main() {
  test('maps a Quality queue job and inspection history record', () {
    final job = QualityWipJobModel.fromJson({
      'id': 1,
      'product_code': 'P1',
      'product_name': 'Part',
      'description': 'Part 1',
      'lot_number': 'LOT-1',
      'lot_segment_code': 'LOT-1-SEG',
      'plant_code': 'PLANT',
      'plant_name': 'Plant',
      'unit': 'pcs',
      'current_quantity': 10,
      'process_name': 'OP 2',
      'can_inspect': true,
    });
    final inspection = QualityInspectionModel.fromJson({
      'id': 1,
      'quality_number': 'QC-210826-000',
      'inspection_date': '2026-08-21',
      'shift': 'Shift 1',
      'description': 'Part 1',
      'lot_number': 'LOT-1',
      'plant_name': 'Plant',
      'unit': 'pcs',
      'inspection_quantity': 10,
      'pass_quantity': 8,
      'repair_quantity': 1,
      'ng_quantity': 1,
      'before_process_name': 'OP 2',
      'repair_process_name': 'Repair OP2',
      'problem': 'Scratch',
      'performed_by_name': 'QC User',
    });
    expect(job.canInspect, isTrue);
    expect(job.quantity, 10);
    expect(inspection.pass, 8);
    expect(inspection.repairProcess, 'Repair OP2');
  });
}
