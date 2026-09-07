import 'package:flutter_test/flutter_test.dart';
import 'package:erp_manufaktur/features/auth/auth_controller.dart';
import 'package:erp_manufaktur/features/purchasing/purchase_order_models.dart';

void main() {
  test('module access maps PIC and Head permissions from backend', () {
    final access = PurchasingAccess.fromJson({
      'can_access': true,
      'is_pic': true,
      'is_head': false,
      'can_review': false,
    });

    expect(access.canAccess, isTrue);
    expect(access.isPic, isTrue);
    expect(access.canReview, isFalse);
  });

  test('purchase order maps list summaries and terminal permissions', () {
    final order = PurchaseOrderModel.fromJson({
      'po_number': 'PO-130826-000',
      'po_date': '2026-08-13',
      'supplier_code': 'SUP',
      'supplier_name': 'Supplier Example',
      'quotation_reference': 'QUOT-01',
      'quotation_date': '2026-08-12',
      'requested_delivery_date': '2026-08-20',
      'delivery_plant_code': 'A1B2C',
      'delivery_plant_name': 'Main Plant',
      'delivery_address': 'Bekasi',
      'notes': '',
      'payment_terms_days': 30,
      'payment_due_date': '2026-09-12',
      'subtotal': '2500.00',
      'discount_amount': '0.00',
      'ppn_rate': '0.000',
      'ppn_amount': '0.00',
      'pph23_rate': '0.000',
      'pph23_amount': '0.00',
      'grand_total': '2500.00',
      'status': 'approved',
      'fulfillment_status': 'open',
      'created_by_name': 'Purchasing PIC',
      'reviewed_by_name': 'Purchasing Head',
      'rejection_reason': null,
      'can_edit': false,
      'can_delete': false,
      'can_review': false,
      'creator_qr_payload': 'creator-token',
      'approval_qr_payload': 'approval-token',
      'items': [
        {
          'id': 1,
          'product_code': 'PRD',
          'part_name': 'Steel Plate',
          'part_no': 'SP-01',
          'description': 'Steel Plate SP-01',
          'quantity_grams': '1000.000',
          'unit': 'pcs',
          'received_quantity': '250.000',
          'outstanding_quantity': '750.000',
          'unit_price': '2.5000',
          'amount': '2500.00',
          'remark': 'Urgent',
        },
      ],
    });

    expect(order.partNames, 'Steel Plate');
    expect(order.partNumbers, 'SP-01');
    expect(order.quantitySummary, '1000 pcs');
    expect(order.items.first.outstandingQuantity, 750);
    expect(order.grandTotal, 2500);
    expect(order.canEdit, isFalse);
    expect(purchaseOrderStatusLabel(order.status), 'Approved');
  });
}
