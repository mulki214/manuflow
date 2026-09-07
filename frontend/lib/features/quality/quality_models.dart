double _quantity(Map<String, dynamic> json, String key) =>
    double.parse(json[key].toString());

class QualityWipJobModel {
  const QualityWipJobModel({
    required this.id,
    required this.productCode,
    required this.productName,
    required this.description,
    required this.lotNumber,
    required this.segmentCode,
    required this.plantCode,
    required this.plantName,
    required this.unit,
    required this.quantity,
    required this.beforeProcess,
    required this.canInspect,
  });

  factory QualityWipJobModel.fromJson(Map<String, dynamic> json) =>
      QualityWipJobModel(
        id: json['id'] as int,
        productCode: json['product_code'].toString(),
        productName: json['product_name'].toString(),
        description: json['description'].toString(),
        lotNumber: json['lot_number'].toString(),
        segmentCode: json['lot_segment_code'].toString(),
        plantCode: json['plant_code'].toString(),
        plantName: json['plant_name'].toString(),
        unit: json['unit'].toString(),
        quantity: _quantity(json, 'current_quantity'),
        beforeProcess: json['process_name'].toString(),
        canInspect: json['can_inspect'] == true,
      );

  final int id;
  final String productCode,
      productName,
      description,
      lotNumber,
      segmentCode,
      plantCode,
      plantName,
      unit,
      beforeProcess;
  final double quantity;
  final bool canInspect;
}

class QualityInspectionModel {
  const QualityInspectionModel({
    required this.id,
    required this.number,
    required this.date,
    required this.shift,
    required this.description,
    required this.lotNumber,
    required this.plantName,
    required this.unit,
    required this.quantity,
    required this.beforeProcess,
    required this.pass,
    required this.repair,
    required this.ng,
    required this.repairProcess,
    required this.problem,
    required this.performedBy,
    required this.isReversed,
    required this.canReverse,
  });

  factory QualityInspectionModel.fromJson(Map<String, dynamic> json) =>
      QualityInspectionModel(
        id: json['id'] as int,
        number: json['quality_number'].toString(),
        date: DateTime.parse(json['inspection_date'].toString()),
        shift: json['shift'].toString(),
        description: json['description'].toString(),
        lotNumber: json['lot_number'].toString(),
        plantName: json['plant_name'].toString(),
        unit: json['unit'].toString(),
        quantity: _quantity(json, 'inspection_quantity'),
        pass: _quantity(json, 'pass_quantity'),
        repair: _quantity(json, 'repair_quantity'),
        ng: _quantity(json, 'ng_quantity'),
        beforeProcess: json['before_process_name'].toString(),
        repairProcess: json['repair_process_name']?.toString(),
        problem: json['problem'].toString(),
        performedBy: json['performed_by_name'].toString(),
        isReversed: json['reversed_at'] != null,
        canReverse: json['can_reverse'] == true,
      );

  final int id;
  final String number,
      shift,
      description,
      lotNumber,
      plantName,
      unit,
      beforeProcess,
      problem,
      performedBy;
  final DateTime date;
  final double quantity, pass, repair, ng;
  final String? repairProcess;
  final bool isReversed, canReverse;
}
