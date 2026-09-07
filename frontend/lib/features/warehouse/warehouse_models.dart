double warehouseNumber(dynamic value) => double.parse(value.toString());

class WarehouseStockLot {
  const WarehouseStockLot({
    required this.id,
    required this.productCode,
    required this.productName,
    required this.description,
    required this.lotNumber,
    required this.quantity,
    required this.unit,
    required this.plantCode,
    required this.plantName,
    required this.storageName,
    required this.locationName,
  });

  factory WarehouseStockLot.fromJson(Map<String, dynamic> json) =>
      WarehouseStockLot(
        id: json['lot_id'] as int,
        productCode: json['product_code'].toString(),
        productName: json['product_name'].toString(),
        description: json['description'].toString(),
        lotNumber: json['lot_number'].toString(),
        quantity: warehouseNumber(json['quantity']),
        unit: json['unit'].toString(),
        plantCode: json['plant_code'].toString(),
        plantName: json['plant_name'].toString(),
        storageName: json['storage_name'].toString(),
        locationName: json['storage_location_name'].toString(),
      );

  final int id;
  final String productCode;
  final String productName;
  final String description;
  final String lotNumber;
  final double quantity;
  final String unit;
  final String plantCode;
  final String plantName;
  final String storageName;
  final String locationName;
}

class WarehouseTransferModel {
  const WarehouseTransferModel({
    required this.number,
    required this.date,
    required this.productCode,
    required this.productName,
    required this.description,
    required this.lotNumber,
    required this.quantity,
    required this.unit,
    required this.plantName,
    required this.source,
    required this.destinationType,
    required this.destination,
    required this.documentNumber,
    required this.notes,
    required this.status,
    required this.performedBy,
    required this.reversalReason,
    required this.wipSegment,
    required this.wipStatus,
    required this.canReverse,
  });

  factory WarehouseTransferModel.fromJson(Map<String, dynamic> json) {
    final destinationType = json['destination_type'].toString();
    return WarehouseTransferModel(
      number: json['transfer_number'].toString(),
      date: DateTime.parse(json['transfer_date'].toString()),
      productCode: json['product_code'].toString(),
      productName: json['product_name'].toString(),
      description: json['description'].toString(),
      lotNumber: json['lot_number'].toString(),
      quantity: warehouseNumber(json['quantity']),
      unit: json['unit'].toString(),
      plantName: json['plant_name'].toString(),
      source:
          '${json['source_storage_name']} — ${json['source_location_name']}',
      destinationType: destinationType,
      destination: destinationType == 'wip'
          ? '${json['destination_process_code']} — ${json['destination_process_name']}'
          : '${json['destination_storage_name']} — ${json['destination_location_name']}',
      documentNumber: json['document_number']?.toString(),
      notes: json['notes']?.toString() ?? '',
      status: json['status'].toString(),
      performedBy: json['performed_by_name'].toString(),
      reversalReason: json['reversal_reason']?.toString(),
      wipSegment: json['wip_lot_segment_code']?.toString(),
      wipStatus: json['wip_status']?.toString(),
      canReverse: json['can_reverse'] == true,
    );
  }

  final String number;
  final DateTime date;
  final String productCode;
  final String productName;
  final String description;
  final String lotNumber;
  final double quantity;
  final String unit;
  final String plantName;
  final String source;
  final String destinationType;
  final String destination;
  final String? documentNumber;
  final String notes;
  final String status;
  final String performedBy;
  final String? reversalReason;
  final String? wipSegment;
  final String? wipStatus;
  final bool canReverse;
}
