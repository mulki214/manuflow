double productionNumber(dynamic value) => double.parse(value.toString());

class ProductionProcessModel {
  const ProductionProcessModel({
    required this.code,
    required this.name,
    required this.description,
    required this.type,
    required this.plantCode,
    required this.plantName,
    required this.isActive,
    required this.canDelete,
  });

  factory ProductionProcessModel.fromJson(Map<String, dynamic> json) =>
      ProductionProcessModel(
        code: json['code'].toString(),
        name: json['name'].toString(),
        description: json['description']?.toString() ?? '',
        type: json['process_type'].toString(),
        plantCode: json['plant_code'].toString(),
        plantName: json['plant_name'].toString(),
        isActive: json['is_active'] == true,
        canDelete: json['can_delete'] == true,
      );

  final String code;
  final String name;
  final String description;
  final String type;
  final String plantCode;
  final String plantName;
  final bool isActive;
  final bool canDelete;
}

class ProductionWipJobModel {
  const ProductionWipJobModel({
    required this.id,
    required this.sourceTransferNumber,
    required this.processCode,
    required this.processName,
    required this.processType,
    required this.productCode,
    required this.productName,
    required this.description,
    required this.lotNumber,
    required this.segmentCode,
    required this.plantCode,
    required this.plantName,
    required this.unit,
    required this.inputQuantity,
    required this.currentQuantity,
    required this.status,
    required this.canComplete,
    this.repairRouteCode,
    this.repairStepOrder,
  });

  factory ProductionWipJobModel.fromJson(Map<String, dynamic> json) =>
      ProductionWipJobModel(
        id: json['id'] as int,
        sourceTransferNumber: json['source_transfer_number'].toString(),
        processCode: json['process_code'].toString(),
        processName: json['process_name'].toString(),
        processType: json['process_type'].toString(),
        productCode: json['product_code'].toString(),
        productName: json['product_name'].toString(),
        description: json['description'].toString(),
        lotNumber: json['lot_number'].toString(),
        segmentCode: json['lot_segment_code'].toString(),
        plantCode: json['plant_code'].toString(),
        plantName: json['plant_name'].toString(),
        unit: json['unit'].toString(),
        inputQuantity: productionNumber(json['input_quantity']),
        currentQuantity: productionNumber(json['current_quantity']),
        status: json['status'].toString(),
        canComplete: json['can_complete'] == true,
        repairRouteCode: json['repair_route_code']?.toString(),
        repairStepOrder: json['repair_step_order'] as int?,
      );

  final int id;
  final String sourceTransferNumber;
  final String processCode;
  final String processName;
  final String processType;
  final String productCode;
  final String productName;
  final String description;
  final String lotNumber;
  final String segmentCode;
  final String plantCode;
  final String plantName;
  final String unit;
  final double inputQuantity;
  final double currentQuantity;
  final String status;
  final bool canComplete;
  final String? repairRouteCode;
  final int? repairStepOrder;
}

class ProductionExecutionModel {
  const ProductionExecutionModel({
    required this.id,
    required this.number,
    required this.date,
    required this.shift,
    required this.productCode,
    required this.description,
    required this.lotNumber,
    required this.segmentCode,
    required this.plantName,
    required this.unit,
    required this.beforeProcess,
    required this.afterProcess,
    required this.machineName,
    required this.processingQuantity,
    required this.goodQuantity,
    required this.repairQuantity,
    required this.ngQuantity,
    required this.performedBy,
    required this.breakDurationMinutes,
    required this.ngLimitExceeded,
    required this.isReversed,
    required this.canReverse,
    this.startedAt,
    this.endedAt,
    this.cycleTimeSeconds,
    this.observedCycleTimeSeconds,
    this.ngOverrideReason,
  });

  factory ProductionExecutionModel.fromJson(Map<String, dynamic> json) =>
      ProductionExecutionModel(
        id: json['id'] as int,
        number: json['production_number'].toString(),
        date: DateTime.parse(json['process_date'].toString()),
        shift: json['shift'].toString(),
        productCode: json['product_code'].toString(),
        description: json['description'].toString(),
        lotNumber: json['lot_number'].toString(),
        segmentCode: json['lot_segment_code'].toString(),
        plantName: json['plant_name'].toString(),
        unit: json['unit'].toString(),
        beforeProcess:
            '${json['before_process_code']} — ${json['before_process_name']}',
        afterProcess: json['after_process_name']?.toString() ?? 'Quality Queue',
        machineName: json['machine_name']?.toString() ?? '-',
        processingQuantity: productionNumber(json['processing_quantity']),
        goodQuantity: productionNumber(json['good_quantity']),
        repairQuantity: productionNumber(json['repair_quantity']),
        ngQuantity: productionNumber(json['ng_quantity']),
        performedBy: json['performed_by_name'].toString(),
        breakDurationMinutes: json['break_duration_minutes'] as int? ?? 0,
        ngLimitExceeded: json['ng_limit_exceeded'] == true,
        isReversed: json['reversed_at'] != null,
        canReverse: json['can_reverse'] == true,
        startedAt: json['started_at'] == null
            ? null
            : DateTime.parse(json['started_at'].toString()),
        endedAt: json['ended_at'] == null
            ? null
            : DateTime.parse(json['ended_at'].toString()),
        cycleTimeSeconds: json['cycle_time_seconds'] == null
            ? null
            : productionNumber(json['cycle_time_seconds']),
        observedCycleTimeSeconds: json['observed_cycle_time_seconds'] == null
            ? null
            : productionNumber(json['observed_cycle_time_seconds']),
        ngOverrideReason: json['ng_override_reason']?.toString(),
      );

  final int id;
  final String number;
  final DateTime date;
  final String shift;
  final String productCode;
  final String description;
  final String lotNumber;
  final String segmentCode;
  final String plantName;
  final String unit;
  final String beforeProcess;
  final String afterProcess;
  final String machineName;
  final double processingQuantity;
  final double goodQuantity;
  final double repairQuantity;
  final double ngQuantity;
  final String performedBy;
  final int breakDurationMinutes;
  final bool ngLimitExceeded;
  final bool isReversed;
  final bool canReverse;
  final DateTime? startedAt;
  final DateTime? endedAt;
  final double? cycleTimeSeconds;
  final double? observedCycleTimeSeconds;
  final String? ngOverrideReason;
}
