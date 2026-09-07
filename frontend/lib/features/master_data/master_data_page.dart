import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../auth/auth_controller.dart';
import '../users/change_password_dialog.dart';
import '../users/user_page.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/crud_widgets.dart';
import '../../shared/module_navigation.dart';
import '../../shared/product_qr_label_dialog.dart';
import 'master_data_form_dialog.dart';
import 'product_bom_dialog.dart';
import 'master_data_models.dart';

class MasterDataPage extends StatefulWidget {
  const MasterDataPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<MasterDataPage> createState() => _MasterDataPageState();
}

class _MasterDataPageState extends State<MasterDataPage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final _search = TextEditingController();
  List<MasterDataRecord> _records = [];
  bool _loading = true;
  String? _error;
  int _page = 1;
  final int _size = 10;
  int _total = 0;

  bool get _isUserTab => _tabs.index == MasterDataType.values.length;
  MasterDataType get _type => MasterDataType.values[_tabs.index];
  int get _totalPages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _tabs = TabController(
      length: MasterDataType.values.length + 1,
      vsync: this,
    );
    _tabs.addListener(() {
      if (!_tabs.indexIsChanging) {
        setState(() {
          _search.clear();
          _page = 1;
        });
        if (!_isUserTab) _load();
      }
    });
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final search = _search.text.trim();
    final query = [
      'page=$_page',
      'size=$_size',
      if (search.isNotEmpty) 'search=${Uri.encodeQueryComponent(search)}',
    ].join('&');
    try {
      final response = await widget.auth.api.getJson(
        '/master-data/${_type.endpoint}?$query',
      );
      if (!mounted) return;
      setState(() {
        _records = (response['items'] as List)
            .map(
              (item) => MasterDataRecord(_type, item as Map<String, dynamic>),
            )
            .toList();
        _total = response['total'] as int;
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
        if (mounted) Navigator.pop(context);
        return;
      }
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to load master data.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm([MasterDataRecord? record]) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => MasterDataFormDialog(
        api: widget.auth.api,
        type: _type,
        record: record,
      ),
    );
    if (changed == true) {
      await _load();
      if (_type == MasterDataType.department) {
        await widget.auth.refreshModuleAccess();
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${_type.label} successfully ${record == null ? 'created' : 'updated'}.',
            ),
          ),
        );
      }
    }
  }

  Future<void> _delete(MasterDataRecord record) async {
    final confirmed = await showDeleteConfirmation(
      context,
      title: 'Delete ${_type.label}?',
      message:
          'Are you sure you want to delete ${record.code} — ${record.name}? This action cannot be undone.',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.delete(
        '/master-data/${_type.endpoint}/${record.code}',
      );
      if (_records.length == 1 && _page > 1) _page--;
      await _load();
      if (_type == MasterDataType.department) {
        await widget.auth.refreshModuleAccess();
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${_type.label} successfully deleted.')),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  void _openDetail(MasterDataRecord record) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Expanded(child: Text('${_type.label} Detail')),
            IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: _detailFields(record)
                  .map(
                    (entry) => Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            entry.$1,
                            style: const TextStyle(
                              color: Color(0xFF667085),
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            entry.$2,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
        ),
        actions: [
          if (_type == MasterDataType.product)
            FilledButton.icon(
              onPressed: () => _openProductQr(record),
              icon: const Icon(Icons.qr_code_2_outlined),
              label: const Text('Download QR'),
            ),
          if (_type == MasterDataType.product &&
              (record.data['category'] == 'finished_good' ||
                  record.data['category'] == 'work_in_progress'))
            OutlinedButton.icon(
              onPressed: record.canEdit
                  ? () async {
                      final changed = await showDialog<bool>(
                        context: context,
                        barrierDismissible: false,
                        builder: (_) => ProductBomDialog(
                          api: widget.auth.api,
                          productCode: record.code,
                        ),
                      );
                      if (changed == true) await _load();
                    }
                  : null,
              icon: const Icon(Icons.account_tree_outlined),
              label: const Text('Bill of Materials'),
            ),
          OutlinedButton.icon(
            onPressed: record.canEdit
                ? () {
                    Navigator.pop(context);
                    _openForm(record);
                  }
                : null,
            icon: const Icon(Icons.edit_outlined),
            label: const Text('Edit'),
          ),
        ],
      ),
    );
  }

  List<(String, String)> _detailFields(MasterDataRecord record) {
    final data = record.data;
    String value(String key) => data[key]?.toString() ?? '-';
    return switch (record.type) {
      MasterDataType.department => [
        ('Department Code', value('code')),
        ('Department Name', value('name')),
        ('PIC Names', (data['pic_names'] as List?)?.join(', ') ?? '-'),
        ('Head Name', value('head_name')),
      ],
      MasterDataType.corporation => [
        ('Corporate Code', value('code')),
        ('Company Name', value('name')),
        ('Business Type', record.subtitle),
        ('Full Address', value('address')),
        ('Company Phone', value('phone_number')),
        ('Contact Person Name', value('contact_person_name')),
        ('Contact Person Phone', value('contact_person_phone')),
        ('NPWP', value('npwp')),
      ],
      MasterDataType.product => [
        ('Product Code', value('code')),
        ('Product Category', value('category').replaceAll('_', ' ')),
        ('Customer Code', value('customer_code')),
        ('Customer Name', value('customer_name')),
        ('Supplier Code', value('supplier_code')),
        ('Supplier Name', value('supplier_name')),
        ('Part Name', value('part_name')),
        ('Part No', value('part_no')),
        ('Description', value('description')),
        ('Gross Weight (g)', value('gross_weight')),
        ('Nett Weight (g)', value('nett_weight')),
        ('Stock Quantity', record.stockLabel),
      ],
      MasterDataType.machine => [
        ('Machine Code', value('code')),
        ('Machine Name', value('name')),
        ('Machine Specification', value('specification')),
        ('Machine Type', value('machine_type')),
        ('Machine Year', value('year')),
        ('Country of Origin', value('country_of_origin')),
        ('Plant Code', value('plant_code')),
        ('Plant Name', value('plant_name')),
      ],
      MasterDataType.plant => [
        ('Plant Code', value('code')),
        ('Plant Name', value('name')),
        ('Plant Full Address', value('full_address')),
      ],
      MasterDataType.warehouseStorage => [
        ('Storage Code', value('code')),
        ('Storage Name', value('name')),
        ('Storage Type', value('storage_type')),
        ('Plant Code', value('plant_code')),
        ('Plant Name', value('plant_name')),
        ('Description', value('description')),
      ],
      MasterDataType.transportation => [
        ('Transportation Code', value('code')),
        ('Vehicle Number', value('vehicle_number')),
        ('Vehicle Type', value('vehicle_type')),
        ('Brand Name', value('brand_name')),
        ('Manufacturing Year', value('manufacturing_year')),
        ('Carrier Name', value('carrier_name')),
        ('Capacity (kg)', value('capacity')),
        ('Notes', value('notes')),
        ('Active', data['is_active'] == true ? 'Yes' : 'No'),
      ],
      MasterDataType.storageLocation => [
        ('Location Code', value('code')),
        ('Location Name', value('name')),
        ('Plant Code', value('plant_code')),
        ('Plant Name', value('plant_name')),
        ('Storage', value('storage_name')),
        ('Storage Type', value('storage_type')),
        ('Description', value('description')),
      ],
    };
  }

  Future<void> _changePassword() async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ChangePasswordDialog(api: widget.auth.api),
    );
    if (changed == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Password successfully updated.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1000;
        final content = _content(desktop);
        if (!desktop) {
          return Scaffold(
            appBar: AppBar(
              leading: IconButton(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.arrow_back),
              ),
              title: const Text(
                'Master Data',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              actions: [
                IconButton(
                  onPressed: _changePassword,
                  icon: const Icon(Icons.password_outlined),
                ),
                IconButton(
                  onPressed: widget.auth.logout,
                  icon: const Icon(Icons.logout),
                ),
              ],
            ),
            body: content,
            floatingActionButton: _isUserTab
                ? null
                : FloatingActionButton.extended(
                    onPressed: _openForm,
                    icon: const Icon(Icons.add),
                    label: Text('Create ${_type.label}'),
                  ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.masterData,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.masterData,
                ),
                onChangePassword: _changePassword,
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('Master Data')),
                  body: content,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _content(bool desktop) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.all(desktop ? 32 : 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Master Data',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        'Manage core manufacturing reference data.',
                        style: TextStyle(color: Color(0xFF667085)),
                      ),
                    ],
                  ),
                ),
                if (desktop && !_isUserTab)
                  FilledButton.icon(
                    onPressed: _openForm,
                    icon: const Icon(Icons.add),
                    label: Text('Create ${_type.label}'),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            TabBar(
              controller: _tabs,
              isScrollable: true,
              tabAlignment: TabAlignment.start,
              tabs: [
                ...MasterDataType.values.map((type) => Tab(text: type.label)),
                const Tab(text: 'User'),
              ],
            ),
            const SizedBox(height: 16),
            if (_isUserTab)
              Expanded(child: UserPage(auth: widget.auth, embedded: true))
            else ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _search,
                          onSubmitted: (_) {
                            _page = 1;
                            _load();
                          },
                          decoration: InputDecoration(
                            hintText:
                                'Filter ${_type.label} by name or code...',
                            prefixIcon: const Icon(Icons.search),
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filledTonal(
                        onPressed: () {
                          _page = 1;
                          _load();
                        },
                        icon: const Icon(Icons.search),
                      ),
                      IconButton(
                        onPressed: _load,
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Expanded(child: _body(desktop)),
              if (!_loading && _error == null) _pagination(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _body(bool desktop) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 48),
            const SizedBox(height: 12),
            Text(_error!),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: _load, child: const Text('Try Again')),
          ],
        ),
      );
    }
    if (_records.isEmpty) {
      return Center(child: Text('No ${_type.label} data found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: ScrollableDataTable(
        child: DataTable(
          showCheckboxColumn: false,
          headingRowColor: WidgetStateProperty.all(const Color(0xFFF9FAFB)),
          columns: [
            const DataColumn(label: Text('CODE')),
            DataColumn(label: Text(_primaryColumnLabel)),
            DataColumn(label: Text(_detailColumnLabel)),
            DataColumn(label: Text(_secondaryColumnLabel)),
            if (_type == MasterDataType.product)
              const DataColumn(label: Text('STOCK QTY')),
            const DataColumn(label: Text('ACTIONS')),
          ],
          rows: _records
              .map(
                (record) => DataRow(
                  onSelectChanged: (_) => _openDetail(record),
                  cells: [
                    DataCell(
                      Text(
                        record.code,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    DataCell(Text(record.name)),
                    DataCell(
                      SizedBox(
                        width: 240,
                        child: Text(
                          record.subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    DataCell(
                      SizedBox(
                        width: 220,
                        child: Text(
                          record.secondary,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    if (_type == MasterDataType.product)
                      DataCell(
                        Text(
                          record.stockLabel,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ),
                    DataCell(_actions(record)),
                  ],
                ),
              )
              .toList(),
        ),
      ),
    );
  }

  Widget _cards() {
    return ListView.separated(
      padding: const EdgeInsets.only(bottom: 88),
      itemCount: _records.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final record = _records[index];
        return Card(
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => _openDetail(record),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  CircleAvatar(
                    child: Text(record.name.isEmpty ? '?' : record.name[0]),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          record.name,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${record.code} • ${record.subtitle}',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Color(0xFF667085),
                            fontSize: 13,
                          ),
                        ),
                        if (record.type == MasterDataType.product) ...[
                          const SizedBox(height: 6),
                          Text(
                            'Stock Qty: ${record.stockLabel}',
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                        ],
                      ],
                    ),
                  ),
                  _actions(record),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _actions(MasterDataRecord record) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (record.type == MasterDataType.product)
          IconButton(
            tooltip: 'Download Product QR',
            onPressed: () => _openProductQr(record),
            icon: const Icon(Icons.qr_code_2_outlined),
          ),
        IconButton(
          tooltip: 'Edit',
          onPressed: record.canEdit ? () => _openForm(record) : null,
          icon: const Icon(Icons.edit_outlined),
        ),
        IconButton(
          tooltip: 'Delete',
          onPressed: record.canDelete ? () => _delete(record) : null,
          color: Theme.of(context).colorScheme.error,
          icon: const Icon(Icons.delete_outline),
        ),
      ],
    );
  }

  void _openProductQr(MasterDataRecord record) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ProductQrLabelPage(
          productCode: record.code,
          productName: record.name,
        ),
      ),
    );
  }

  String get _primaryColumnLabel => switch (_type) {
    MasterDataType.department => 'DEPARTMENT NAME',
    MasterDataType.corporation => 'COMPANY NAME',
    MasterDataType.product => 'PART NAME',
    MasterDataType.machine => 'MACHINE NAME',
    MasterDataType.plant => 'PLANT NAME',
    MasterDataType.warehouseStorage => 'STORAGE NAME',
    MasterDataType.transportation => 'VEHICLE NUMBER',
    MasterDataType.storageLocation => 'LOCATION NAME',
  };

  String get _detailColumnLabel => switch (_type) {
    MasterDataType.department => 'PIC',
    MasterDataType.corporation => 'ADDRESS',
    MasterDataType.product => 'CUSTOMER / SUPPLIER',
    MasterDataType.machine => 'MACHINE TYPE',
    MasterDataType.plant => 'ADDRESS',
    MasterDataType.warehouseStorage => 'TYPE / PLANT',
    MasterDataType.transportation => 'TYPE / BRAND',
    MasterDataType.storageLocation => 'DESCRIPTION',
  };

  String get _secondaryColumnLabel => switch (_type) {
    MasterDataType.department => 'HEAD',
    MasterDataType.corporation => 'CONTACT PERSON',
    MasterDataType.product => 'DESCRIPTION',
    MasterDataType.machine => 'PLANT',
    MasterDataType.plant => '',
    MasterDataType.warehouseStorage => 'DESCRIPTION',
    MasterDataType.transportation => 'CARRIER',
    MasterDataType.storageLocation => 'PLANT',
  };

  Widget _pagination() {
    return CrudPaginationBar(
      currentPage: _page,
      totalPages: _totalPages,
      totalRecords: _total,
      onPrevious: _page > 1
          ? () {
              _page--;
              _load();
            }
          : null,
      onNext: _page < _totalPages
          ? () {
              _page++;
              _load();
            }
          : null,
    );
  }
}
