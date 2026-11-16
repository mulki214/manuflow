import 'package:flutter_test/flutter_test.dart';
import 'package:erp_manufaktur/shared/select_option_labels.dart';

void main() {
  test('order item label starts with internal SO then customer PO', () {
    final label = orderItemSelectLabel({
      'internal_document_number': 'SO-161126-001',
      'document_number': 'CUSTOMER-PO-001',
      'product_code': 'B002',
      'product_description': 'BOSS BPN-E7673-00',
    }, quantity: '30000 pcs');

    expect(
      label,
      'SO-161126-001 — CUSTOMER-PO-001 — B002 — BOSS BPN-E7673-00 — 30000 pcs',
    );
  });

  test('order item label does not duplicate an identical internal number', () {
    final label = orderItemSelectLabel({
      'internal_document_number': 'PO-161126-001',
      'document_number': 'PO-161126-001',
      'product_code': 'B002',
    }, quantity: '10 pcs');

    expect(label, 'PO-161126-001 — B002 — 10 pcs');
  });
}
