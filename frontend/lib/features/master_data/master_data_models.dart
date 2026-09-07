enum MasterDataType {
  department('Department', 'departments'),
  corporation('Corporation', 'corporations'),
  product('Product', 'products'),
  machine('Machine', 'machines'),
  plant('Plant', 'plants'),
  warehouseStorage('Storage / Warehouse', 'warehouse-storages'),
  transportation('Transportation', 'transportations'),
  storageLocation('Storage Location', 'storage-locations');

  const MasterDataType(this.label, this.endpoint);
  final String label;
  final String endpoint;
}

class MasterDataRecord {
  const MasterDataRecord(this.type, this.data);

  final MasterDataType type;
  final Map<String, dynamic> data;

  String get code => data['code']?.toString() ?? '';

  String get name => switch (type) {
    MasterDataType.product => data['part_name']?.toString() ?? '',
    MasterDataType.transportation => data['vehicle_number']?.toString() ?? '',
    _ => data['name']?.toString() ?? '',
  };

  String get subtitle => switch (type) {
    MasterDataType.department =>
      'PIC: ${_listValue('pic_names')} • Head: ${value('head_name')}',
    MasterDataType.corporation => value('address'),
    MasterDataType.product =>
      value('supply_source') == 'manufactured_internally'
          ? '${value('customer_name')} • Manufactured internally'
          : '${value('customer_name')} • ${value('supplier_name')}',
    MasterDataType.machine =>
      '${value('machine_type')} • ${value('plant_name')}',
    MasterDataType.plant => data['full_address']?.toString() ?? '',
    MasterDataType.warehouseStorage =>
      '${value('storage_type')} • ${value('plant_name')}',
    MasterDataType.transportation =>
      '${value('vehicle_type')} • ${value('brand_name')}',
    MasterDataType.storageLocation => value('description'),
  };

  String get secondary => switch (type) {
    MasterDataType.department => 'Head: ${value('head_name')}',
    MasterDataType.corporation =>
      '${value('contact_person_name')} • ${value('contact_person_phone')}',
    MasterDataType.product => value('description'),
    MasterDataType.machine => value('plant_name'),
    MasterDataType.plant => '',
    MasterDataType.warehouseStorage => value('description'),
    MasterDataType.transportation => value('carrier_name'),
    MasterDataType.storageLocation => value('plant_name'),
  };

  bool get canEdit => data['can_edit'] == true;
  bool get canDelete => data['can_delete'] == true;

  String get stockLabel {
    final balances = data['stock_by_unit'];
    if (balances is! Map || balances.isEmpty) return '0';
    return balances.entries
        .map((entry) => '${_quantity(entry.value)} ${entry.key}')
        .join(' • ');
  }

  String _listValue(String key) {
    final values = data[key];
    if (values is List && values.isNotEmpty) return values.join(', ');
    return '-';
  }

  static String _quantity(dynamic value) {
    final number = double.tryParse(value.toString()) ?? 0;
    return number.toStringAsFixed(3).replaceFirst(RegExp(r'\.?0+$'), '');
  }

  String value(String key) => data[key]?.toString() ?? '-';
}

class LookupOption {
  const LookupOption({required this.code, required this.name});
  final String code;
  final String name;

  String get label => '$code — $name';
}
