import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/crud_widgets.dart';
import '../../shared/mobile_product_scanner.dart';
import '../../shared/module_navigation.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';
import '../master_data/master_data_page.dart';
import '../purchasing/purchasing_page.dart';
import '../sales_order/sales_order_page.dart';
import '../users/change_password_dialog.dart';
import '../warehouse/warehouse_page.dart';
import '../production/production_page.dart';
import '../quality/quality_page.dart';
import 'receiving_form_dialog.dart';
import 'receiving_models.dart';

class ReceivingPage extends StatefulWidget {
  const ReceivingPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<ReceivingPage> createState() => _ReceivingPageState();
}

class _ReceivingPageState extends State<ReceivingPage> {
  final _search = TextEditingController();
  List<ReceivingModel> _records = [];
  List<Map<String, dynamic>> _products = [];
  bool _checking = true;
  bool _allowed = false;
  bool _loading = false;
  String? _error;
  String? _productCode;
  DateTime? _dateFrom;
  DateTime? _dateTo;
  int _page = 1;
  final int _size = 10;
  int _total = 0;

  int get _totalPages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _verify();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    try {
      final access = await widget.auth.refreshReceivingAccess();
      if (!mounted) return;
      _allowed = access.canAccess;
      if (_allowed) {
        final products = await widget.auth.api.getJson(
          '/master-data/products?size=100',
        );
        _products = List<Map<String, dynamic>>.from(products['items'] as List);
        await _load();
      }
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
        return;
      }
      _error = exception.message;
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  String _apiDate(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final term = _search.text.trim();
    final query = [
      'page=$_page',
      'size=$_size',
      if (term.isNotEmpty) 'search=${Uri.encodeQueryComponent(term)}',
      if (_productCode != null) 'product_code=$_productCode',
      if (_dateFrom != null) 'date_from=${_apiDate(_dateFrom!)}',
      if (_dateTo != null) 'date_to=${_apiDate(_dateTo!)}',
    ].join('&');
    try {
      final response = await widget.auth.api.getJson('/receiving?$query');
      if (!mounted) return;
      setState(() {
        _records = (response['items'] as List)
            .map(
              (item) => ReceivingModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _total = response['total'] as int;
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 403) _allowed = false;
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create({List<String> scannedProductCodes = const []}) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ReceivingFormDialog(
        auth: widget.auth,
        scannedProductCodes: scannedProductCodes,
      ),
    );
    if (changed == true) {
      await _load();
      _message('Receiving posted and inventory stock updated.');
    }
  }

  Future<void> _scanReceiving() async {
    final scans = await scanProducts(context, widget.auth.api);
    if (scans == null || scans.isEmpty) return;
    await _create(
      scannedProductCodes: scans
          .map((item) => item.productCode)
          .toSet()
          .toList(),
    );
  }

  Future<void> _reverse(ReceivingModel record) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reverse Receiving?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${record.quantityGrams} ${unitLabel(record.unit)} will be removed from Lot ${record.lotNumber} and Product ${record.productCode}.',
            ),
            const SizedBox(height: 14),
            TextField(
              controller: controller,
              minLines: 3,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: 'Reversal Reason',
                helperText: 'Minimum 3 characters',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              if (controller.text.trim().length >= 3) {
                Navigator.pop(context, controller.text.trim());
              }
            },
            child: const Text('Reverse Stock'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null) return;
    try {
      await widget.auth.api.postJson(
        '/receiving/${record.receiptNumber}/reverse',
        {'reason': reason},
      );
      await _load();
      _message('Receiving reversed and inventory stock updated.');
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  void _message(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  Future<void> _pickRange() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2200),
      initialDateRange: _dateFrom == null || _dateTo == null
          ? null
          : DateTimeRange(start: _dateFrom!, end: _dateTo!),
    );
    if (range != null) {
      _dateFrom = range.start;
      _dateTo = range.end;
      _page = 1;
      await _load();
    }
  }

  Future<void> _changePassword() => showDialog<bool>(
    context: context,
    builder: (_) => ChangePasswordDialog(api: widget.auth.api),
  );

  void _selectModule(AppModule module) {
    if (module == AppModule.user) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    } else if (module == AppModule.masterData) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => MasterDataPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.purchasing &&
        widget.auth.canAccessPurchasing) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => PurchasingPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.salesOrder &&
        widget.auth.canAccessSalesOrder) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => SalesOrderPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.warehouse &&
        widget.auth.canAccessWarehouse) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => WarehousePage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.production &&
        widget.auth.canAccessProduction) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => ProductionPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.quality && widget.auth.canAccessQuality) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => QualityPage(auth: widget.auth)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_allowed) return _denied();
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1000;
        if (!desktop) {
          return Scaffold(
            appBar: AppBar(title: const Text('Receiving')),
            drawer: _ReceivingDrawer(
              auth: widget.auth,
              onSelected: _selectModule,
            ),
            body: _content(desktop),
            floatingActionButton: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (supportsMobileProductScanner) ...[
                  FloatingActionButton.small(
                    heroTag: 'scan-receiving',
                    onPressed: _scanReceiving,
                    child: const Icon(Icons.qr_code_scanner),
                  ),
                  const SizedBox(height: 12),
                ],
                FloatingActionButton.extended(
                  heroTag: 'create-receiving',
                  onPressed: _create,
                  icon: const Icon(Icons.add),
                  label: const Text('Receive'),
                ),
              ],
            ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.receiving,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.receiving,
                ),
                onChangePassword: _changePassword,
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('Receiving')),
                  body: _content(desktop),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _denied() => Scaffold(
    appBar: AppBar(title: const Text('Receiving')),
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.lock_outline, size: 64),
          const SizedBox(height: 12),
          const Text(
            'Access Denied',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            _error ??
                'Only active Warehouse Department members can access Receiving.',
          ),
        ],
      ),
    ),
  );

  Widget _content(bool desktop) => SafeArea(
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
                      'Receiving',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    Text(
                      '$_total records • stock follows each Receiving unit',
                      style: const TextStyle(color: Color(0xFF667085)),
                    ),
                  ],
                ),
              ),
              if (desktop)
                FilledButton.icon(
                  onPressed: _create,
                  icon: const Icon(Icons.add),
                  label: const Text('Receive Product'),
                ),
            ],
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  SizedBox(
                    width: desktop ? 330 : double.infinity,
                    child: TextField(
                      controller: _search,
                      decoration: const InputDecoration(
                        hintText: 'Receipt, lot, document, or PO...',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onSubmitted: (_) => _load(),
                    ),
                  ),
                  SizedBox(
                    width: desktop ? 230 : double.infinity,
                    child: DropdownButtonFormField<String?>(
                      decoration: const InputDecoration(labelText: 'Product'),
                      initialValue: _productCode,
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('All Products'),
                        ),
                        ..._products.map(
                          (item) => DropdownMenuItem(
                            value: item['code'].toString(),
                            child: Text(
                              item['part_name'].toString(),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                      ],
                      onChanged: (value) {
                        _productCode = value;
                        _page = 1;
                        _load();
                      },
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: _pickRange,
                    icon: const Icon(Icons.date_range_outlined),
                    label: Text(
                      _dateFrom == null
                          ? 'Receipt Date Range'
                          : '${_displayDate(_dateFrom!)} – ${_displayDate(_dateTo!)}',
                    ),
                  ),
                  IconButton.filledTonal(
                    onPressed: _load,
                    icon: const Icon(Icons.search),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Expanded(child: _body(desktop)),
          if (!_loading && _error == null)
            CrudPaginationBar(
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
            ),
        ],
      ),
    ),
  );

  Widget _body(bool desktop) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    if (_records.isEmpty) {
      return const Center(child: Text('No Receiving records found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() => Card(
    child: ScrollableDataTable(
      child: DataTable(
        showCheckboxColumn: false,
        columns: const [
          DataColumn(label: Text('RECEIPT')),
          DataColumn(label: Text('DATE')),
          DataColumn(label: Text('PRODUCT / DESCRIPTION')),
          DataColumn(label: Text('LOT')),
          DataColumn(label: Text('QTY (GRAM)')),
          DataColumn(label: Text('PLANT / LOCATION')),
          DataColumn(label: Text('SOURCE / DOCUMENT')),
          DataColumn(label: Text('PO / VEHICLE / DRIVER')),
          DataColumn(label: Text('RECEIVER')),
          DataColumn(label: Text('STATUS')),
          DataColumn(label: Text('ACTION')),
        ],
        rows: _records
            .map(
              (record) => DataRow(
                onSelectChanged: (_) => _detailDialog(record),
                cells: [
                  DataCell(
                    Text(
                      record.receiptNumber,
                      style: const TextStyle(fontFamily: 'monospace'),
                    ),
                  ),
                  DataCell(Text(_displayDate(record.receiptDate))),
                  DataCell(
                    SizedBox(
                      width: 220,
                      child: Text(
                        '${record.productCode} — ${record.productName}\n${record.description}',
                        maxLines: 3,
                      ),
                    ),
                  ),
                  DataCell(Text(record.lotNumber)),
                  DataCell(Text(_number(record.quantityGrams))),
                  DataCell(
                    Text('${record.plantName}\n${record.storageLocationName}'),
                  ),
                  DataCell(
                    Text('${record.source}\n${record.documentNumber ?? '-'}'),
                  ),
                  DataCell(
                    Text(
                      '${record.poNumber ?? '-'}\n${record.vehicleNumber ?? '-'} • ${record.driverName ?? '-'}',
                    ),
                  ),
                  DataCell(Text(record.receiverName)),
                  DataCell(_statusChip(record.status)),
                  DataCell(
                    IconButton(
                      tooltip: 'Reverse',
                      onPressed: record.canReverse
                          ? () => _reverse(record)
                          : null,
                      icon: const Icon(Icons.undo_outlined),
                    ),
                  ),
                ],
              ),
            )
            .toList(),
      ),
    ),
  );

  Widget _cards() => ListView.separated(
    padding: const EdgeInsets.only(bottom: 88),
    itemCount: _records.length,
    separatorBuilder: (_, _) => const SizedBox(height: 10),
    itemBuilder: (context, index) {
      final record = _records[index];
      return Card(
        child: ListTile(
          onTap: () => _detailDialog(record),
          title: Text(record.receiptNumber),
          subtitle: Text(
            '${record.productName} • Lot ${record.lotNumber}\n${_number(record.quantityGrams)} ${unitLabel(record.unit)} • ${record.storageLocationName}',
          ),
          trailing: _statusChip(record.status),
        ),
      );
    },
  );

  Widget _statusChip(String value) {
    final color = value == 'posted'
        ? const Color(0xFF067647)
        : const Color(0xFFB42318);
    return Chip(
      label: Text(receivingStatusLabel(value)),
      labelStyle: TextStyle(color: color, fontSize: 12),
      backgroundColor: color.withValues(alpha: 0.08),
    );
  }

  void _detailDialog(ReceivingModel record) {
    final fields = <(String, String)>[
      ('Receipt Number', record.receiptNumber),
      ('Receipt Date', _displayDate(record.receiptDate)),
      ('Product', '${record.productCode} — ${record.productName}'),
      ('Description', record.description),
      ('Lot Number', record.lotNumber),
      (
        'Quantity',
        '${_number(record.quantityGrams)} ${unitLabel(record.unit)}',
      ),
      ('Plant', '${record.plantCode} — ${record.plantName}'),
      (
        'Storage Location',
        '${record.storageLocationCode} — ${record.storageLocationName}',
      ),
      ('From / Source', record.source),
      ('Document Number', record.documentNumber ?? '-'),
      ('PO Number', record.poNumber ?? '-'),
      (
        'Vehicle / Driver',
        '${record.vehicleNumber ?? '-'} / ${record.driverName ?? '-'}',
      ),
      ('Receiver', record.receiverName),
      (
        'Lot Stock After',
        '${_number(record.lotStockAfterGrams)} ${unitLabel(record.unit)}',
      ),
      ('Notes', record.notes.isEmpty ? '-' : record.notes),
      if (record.reversalReason != null)
        ('Reversal Reason', record.reversalReason!),
    ];
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Expanded(child: Text(record.receiptNumber)),
            _statusChip(record.status),
          ],
        ),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700, maxHeight: 650),
          child: SingleChildScrollView(
            child: Wrap(
              spacing: 24,
              runSpacing: 14,
              children: fields
                  .map(
                    (field) => SizedBox(
                      width: 300,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            field.$1,
                            style: const TextStyle(
                              color: Color(0xFF667085),
                              fontSize: 12,
                            ),
                          ),
                          Text(
                            field.$2,
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
          if (record.canReverse)
            FilledButton.icon(
              onPressed: () {
                Navigator.pop(context);
                _reverse(record);
              },
              icon: const Icon(Icons.undo),
              label: const Text('Reverse'),
            ),
        ],
      ),
    );
  }

  String _displayDate(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
  String _number(double value) =>
      value.toStringAsFixed(value.truncateToDouble() == value ? 0 : 3);
}

class _ReceivingDrawer extends StatelessWidget {
  const _ReceivingDrawer({required this.auth, required this.onSelected});
  final AuthController auth;
  final ValueChanged<AppModule> onSelected;

  @override
  Widget build(BuildContext context) => Drawer(
    child: SafeArea(
      child: ListView(
        children: AppModule.values
            .where(
              (module) => switch (module) {
                AppModule.purchasing => auth.canAccessPurchasing,
                AppModule.salesOrder => auth.canAccessSalesOrder,
                AppModule.receiving => auth.canAccessReceiving,
                AppModule.warehouse => auth.canAccessWarehouse,
                AppModule.production => auth.canAccessProduction,
                _ => true,
              },
            )
            .map(
              (module) => ListTile(
                selected: module == AppModule.receiving,
                leading: Icon(module.icon),
                title: Text(module.label),
                onTap: () {
                  Navigator.pop(context);
                  if (module != AppModule.receiving) onSelected(module);
                },
              ),
            )
            .toList(),
      ),
    ),
  );
}
