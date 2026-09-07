import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/crud_widgets.dart';
import '../../shared/module_navigation.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';
import '../master_data/master_data_page.dart';
import '../production/production_page.dart';
import '../quality/quality_page.dart';
import '../purchasing/purchasing_page.dart';
import '../receiving/receiving_page.dart';
import '../sales_order/sales_order_page.dart';
import '../users/change_password_dialog.dart';
import 'warehouse_models.dart';
import 'warehouse_transfer_form_dialog.dart';

class WarehousePage extends StatefulWidget {
  const WarehousePage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<WarehousePage> createState() => _WarehousePageState();
}

class _WarehousePageState extends State<WarehousePage> {
  final _search = TextEditingController();
  List<WarehouseTransferModel> _transfers = [];
  bool _checking = true;
  bool _allowed = false;
  bool _loading = false;
  String? _error;
  String? _status;
  String? _destination;
  DateTime? _from;
  DateTime? _to;
  int _page = 1;
  int _total = 0;
  final int _size = 10;

  int get _pages => _total == 0 ? 1 : (_total / _size).ceil();

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
      final access = await widget.auth.refreshWarehouseAccess();
      if (!mounted) return;
      _allowed = access.canAccess;
      if (_allowed) await _load();
    } on ApiException catch (exception) {
      if (mounted) _error = exception.message;
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final term = _search.text.trim();
      final query = [
        'page=$_page',
        'size=$_size',
        if (term.isNotEmpty) 'search=${Uri.encodeQueryComponent(term)}',
        if (_status != null) 'status=$_status',
        if (_destination != null) 'destination_type=$_destination',
        if (_from != null) 'date_from=${_apiDate(_from!)}',
        if (_to != null) 'date_to=${_apiDate(_to!)}',
      ].join('&');
      final response = await widget.auth.api.getJson('/warehouse?$query');
      if (!mounted) return;
      setState(() {
        _transfers = (response['items'] as List)
            .map(
              (item) =>
                  WarehouseTransferModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _total = response['total'] as int;
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
      } else if (exception.statusCode == 403) {
        if (mounted) setState(() => _allowed = false);
      } else if (mounted) {
        setState(() => _error = exception.message);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => WarehouseTransferFormDialog(api: widget.auth.api),
    );
    if (changed == true) {
      await _load();
      _message('Material Transfer posted.');
    }
  }

  Future<void> _reverse(WarehouseTransferModel transfer) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reverse Material Transfer?'),
        content: TextField(
          controller: controller,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Reason *'),
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
            child: const Text('Reverse'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null) return;
    try {
      await widget.auth.api.postJson('/warehouse/${transfer.number}/reverse', {
        'reason': reason,
      });
      await _load();
      _message('Material Transfer reversed.');
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  void _message(String value) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(value)));
    }
  }

  // ignore: unused_element
  void _selectModule(AppModule module) {
    Widget? page;
    if (module == AppModule.user) {
      Navigator.of(context).popUntil((route) => route.isFirst);
      return;
    }
    if (module == AppModule.masterData) {
      page = MasterDataPage(auth: widget.auth);
    }
    if (module == AppModule.purchasing && widget.auth.canAccessPurchasing) {
      page = PurchasingPage(auth: widget.auth);
    }
    if (module == AppModule.salesOrder && widget.auth.canAccessSalesOrder) {
      page = SalesOrderPage(auth: widget.auth);
    }
    if (module == AppModule.receiving && widget.auth.canAccessReceiving) {
      page = ReceivingPage(auth: widget.auth);
    }
    if (module == AppModule.production && widget.auth.canAccessProduction) {
      page = ProductionPage(auth: widget.auth);
    }
    if (module == AppModule.quality && widget.auth.canAccessQuality) {
      page = QualityPage(auth: widget.auth);
    }
    if (page != null) {
      Navigator.of(
        context,
      ).pushReplacement(MaterialPageRoute<void>(builder: (_) => page!));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_allowed) {
      return Scaffold(
        appBar: AppBar(title: const Text('Warehouse')),
        body: Center(
          child: Text(
            _error ??
                'Only active Warehouse Department members can access this module.',
          ),
        ),
      );
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1000;
        final content = _content(desktop);
        if (!desktop) {
          return Scaffold(
            appBar: AppBar(title: const Text('Warehouse')),
            drawer: Drawer(
              child: SafeArea(
                child: AppSidebar(
                  auth: widget.auth,
                  activeModule: AppModule.warehouse,
                  onModuleSelected: (module) => navigateToModule(
                    context,
                    widget.auth,
                    module,
                    activeModule: AppModule.warehouse,
                  ),
                ),
              ),
            ),
            body: content,
            floatingActionButton: FloatingActionButton.extended(
              onPressed: _create,
              icon: const Icon(Icons.add),
              label: const Text('Transfer'),
            ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.warehouse,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.warehouse,
                ),
                onChangePassword: () => showDialog<bool>(
                  context: context,
                  builder: (_) => ChangePasswordDialog(api: widget.auth.api),
                ),
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('Warehouse')),
                  body: content,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

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
                      'Warehouse / Storage Material',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '$_total material transfers',
                      style: const TextStyle(color: Color(0xFF667085)),
                    ),
                  ],
                ),
              ),
              if (desktop)
                FilledButton.icon(
                  onPressed: _create,
                  icon: const Icon(Icons.add),
                  label: Text('Create Transfer'),
                ),
            ],
          ),
          const SizedBox(height: 14),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Wrap(
                spacing: 10,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 330,
                    child: TextField(
                      controller: _search,
                      onSubmitted: (_) => _load(),
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search),
                        hintText: 'Search number, product, lot, or process...',
                        isDense: true,
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 150,
                    child: DropdownButtonFormField<String?>(
                      initialValue: _status,
                      decoration: const InputDecoration(
                        labelText: 'Status',
                        isDense: true,
                      ),
                      items: const [
                        DropdownMenuItem(value: null, child: Text('All')),
                        DropdownMenuItem(
                          value: 'posted',
                          child: Text('Posted'),
                        ),
                        DropdownMenuItem(
                          value: 'reversed',
                          child: Text('Reversed'),
                        ),
                      ],
                      onChanged: (value) {
                        _status = value;
                        _page = 1;
                        _load();
                      },
                    ),
                  ),
                  SizedBox(
                    width: 180,
                    child: DropdownButtonFormField<String?>(
                      initialValue: _destination,
                      decoration: const InputDecoration(
                        labelText: 'Destination',
                        isDense: true,
                      ),
                      items: const [
                        DropdownMenuItem(value: null, child: Text('All')),
                        DropdownMenuItem(value: 'wip', child: Text('WIP')),
                        DropdownMenuItem(
                          value: 'finished_goods',
                          child: Text('Finished Goods'),
                        ),
                      ],
                      onChanged: (value) {
                        _destination = value;
                        _page = 1;
                        _load();
                      },
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: _pickRange,
                    icon: const Icon(Icons.date_range),
                    label: Text(
                      _from == null
                          ? 'Date Range'
                          : '${_date(_from!)} – ${_date(_to!)}',
                    ),
                  ),
                  IconButton.filledTonal(
                    onPressed: _load,
                    icon: const Icon(Icons.search),
                  ),
                  IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Expanded(child: _body(desktop)),
          if (!_loading && _error == null)
            CrudPaginationBar(
              currentPage: _page,
              totalPages: _pages,
              totalRecords: _total,
              onPrevious: _page > 1
                  ? () {
                      _page--;
                      _load();
                    }
                  : null,
              onNext: _page < _pages
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
    if (_transfers.isEmpty) {
      return const Center(child: Text('No Material Transfers found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() => Card(
    clipBehavior: Clip.antiAlias,
    child: ScrollableDataTable(
      child: DataTable(
        showCheckboxColumn: false,
        columns: const [
          DataColumn(label: Text('DATE')),
          DataColumn(label: Text('TRANSFER NO')),
          DataColumn(label: Text('PRODUCT / DESCRIPTION')),
          DataColumn(label: Text('LOT')),
          DataColumn(label: Text('QTY / UNIT')),
          DataColumn(label: Text('PLANT')),
          DataColumn(label: Text('BEFORE PROCESS')),
          DataColumn(label: Text('AFTER PROCESS')),
          DataColumn(label: Text('DOCUMENT')),
          DataColumn(label: Text('STATUS')),
          DataColumn(label: Text('ACTIONS')),
        ],
        rows: _transfers
            .map(
              (item) => DataRow(
                onSelectChanged: (_) => _detail(item),
                cells: [
                  DataCell(Text(_date(item.date))),
                  DataCell(
                    Text(
                      item.number,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  DataCell(
                    SizedBox(
                      width: 220,
                      child: Text(
                        '${item.productCode} — ${item.description}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                  DataCell(Text(item.lotNumber)),
                  DataCell(
                    Text('${_number(item.quantity)} ${unitLabel(item.unit)}'),
                  ),
                  DataCell(Text(item.plantName)),
                  DataCell(Text(item.source)),
                  DataCell(Text(item.destination)),
                  DataCell(Text(item.documentNumber ?? '-')),
                  DataCell(_statusChip(item.status)),
                  DataCell(
                    IconButton(
                      onPressed: item.canReverse ? () => _reverse(item) : null,
                      tooltip: 'Reverse',
                      icon: const Icon(Icons.undo),
                    ),
                  ),
                ],
              ),
            )
            .toList(),
      ),
    ),
  );

  Widget _cards() {
    return ListView.separated(
      padding: const EdgeInsets.only(bottom: 88),
      itemCount: _transfers.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final item = _transfers[index];
        return Card(
          child: ListTile(
            onTap: () => _detail(item),
            title: Text(item.number),
            subtitle: Text(
              '${item.description}\nLot ${item.lotNumber} • ${_number(item.quantity)} ${unitLabel(item.unit)}\n${item.source} → ${item.destination}',
            ),
            isThreeLine: true,
            trailing: _statusChip(item.status),
          ),
        );
      },
    );
  }

  void _detail(WarehouseTransferModel item) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Expanded(child: Text(item.number)),
            _statusChip(item.status),
          ],
        ),
        content: SizedBox(
          width: 720,
          child: SingleChildScrollView(
            child: Wrap(
              spacing: 24,
              runSpacing: 16,
              children: [
                _detailItem('Date', _date(item.date)),
                _detailItem(
                  'Product',
                  '${item.productCode} — ${item.productName}',
                ),
                _detailItem('Description', item.description),
                _detailItem('Lot', item.lotNumber),
                _detailItem(
                  'Quantity',
                  '${_number(item.quantity)} ${unitLabel(item.unit)}',
                ),
                _detailItem('Plant', item.plantName),
                _detailItem('Before Process', item.source),
                _detailItem('After Process', item.destination),
                _detailItem('Document', item.documentNumber ?? '-'),
                _detailItem('Performed By', item.performedBy),
                if (item.wipSegment != null)
                  _detailItem(
                    'WIP Segment',
                    '${item.wipSegment}\n${item.wipStatus}',
                  ),
                if (item.notes.isNotEmpty) _detailItem('Notes', item.notes),
                if (item.reversalReason != null)
                  _detailItem('Reversal Reason', item.reversalReason!),
              ],
            ),
          ),
        ),
        actions: [
          if (item.canReverse)
            OutlinedButton.icon(
              onPressed: () {
                Navigator.pop(context);
                _reverse(item);
              },
              icon: const Icon(Icons.undo),
              label: const Text('Reverse'),
            ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _detailItem(String label, String value) => SizedBox(
    width: 210,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: Color(0xFF667085), fontSize: 12),
        ),
        const SizedBox(height: 3),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ],
    ),
  );
  Widget _statusChip(String value) {
    final posted = value == 'posted';
    final color = posted ? const Color(0xFF067647) : const Color(0xFF475467);
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(posted ? 'Posted' : 'Reversed'),
      labelStyle: TextStyle(color: color),
      backgroundColor: color.withValues(alpha: .08),
    );
  }

  Future<void> _pickRange() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2200),
    );
    if (range != null) {
      _from = range.start;
      _to = range.end;
      _page = 1;
      await _load();
    }
  }

  String _apiDate(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
  String _date(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
  String _number(double value) => value == value.truncateToDouble()
      ? value.toInt().toString()
      : value.toString();
}
