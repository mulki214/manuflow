class ReceivingModel {
  const ReceivingModel({
    required this.receiptNumber,
    required this.receiptDate,
    required this.productCode,
    required this.productName,
    required this.description,
    required this.lotNumber,
    required this.quantityGrams,
    required this.unit,
    required this.plantCode,
    required this.plantName,
    required this.storageLocationCode,
    required this.storageLocationName,
    required this.source,
    required this.sourceType,
    required this.sourceCode,
    required this.documentNumber,
    required this.poNumber,
    required this.vehicleNumber,
    required this.transportSource,
    required this.driverName,
    required this.notes,
    required this.receiverName,
    required this.status,
    required this.reversalReason,
    required this.productStockAfterGrams,
    required this.lotStockAfterGrams,
    required this.canReverse,
  });

  factory ReceivingModel.fromJson(Map<String, dynamic> json) => ReceivingModel(
    receiptNumber: json['receipt_number'].toString(),
    receiptDate: DateTime.parse(json['receipt_date'].toString()),
    productCode: json['product_code'].toString(),
    productName: json['product_name'].toString(),
    description: json['description'].toString(),
    lotNumber: json['lot_number'].toString(),
    quantityGrams: _number(json['quantity_grams']),
    unit: json['unit'].toString(),
    plantCode: json['plant_code'].toString(),
    plantName: json['plant_name'].toString(),
    storageLocationCode: json['storage_location_code'].toString(),
    storageLocationName: json['storage_location_name'].toString(),
    source: json['source'].toString(),
    sourceType: json['source_type']?.toString(),
    sourceCode: json['source_code']?.toString(),
    documentNumber: json['document_number']?.toString(),
    poNumber: json['po_number']?.toString(),
    vehicleNumber: json['vehicle_number']?.toString(),
    transportSource: json['transport_source']?.toString() ?? 'external',
    driverName: json['driver_name']?.toString(),
    notes: json['notes']?.toString() ?? '',
    receiverName: json['receiver_name'].toString(),
    status: json['status'].toString(),
    reversalReason: json['reversal_reason']?.toString(),
    productStockAfterGrams: _number(json['product_stock_after_grams']),
    lotStockAfterGrams: _number(json['lot_stock_after_grams']),
    canReverse: json['can_reverse'] == true,
  );

  final String receiptNumber;
  final DateTime receiptDate;
  final String productCode;
  final String productName;
  final String description;
  final String lotNumber;
  final double quantityGrams;
  final String unit;
  final String plantCode;
  final String plantName;
  final String storageLocationCode;
  final String storageLocationName;
  final String source;
  final String? sourceType;
  final String? sourceCode;
  final String? documentNumber;
  final String? poNumber;
  final String? vehicleNumber;
  final String transportSource;
  final String? driverName;
  final String notes;
  final String receiverName;
  final String status;
  final String? reversalReason;
  final double productStockAfterGrams;
  final double lotStockAfterGrams;
  final bool canReverse;
}

double _number(dynamic value) => double.parse(value.toString());

String receivingStatusLabel(String value) => switch (value) {
  'posted' => 'Posted',
  'reversed' => 'Reversed',
  _ => value,
};
