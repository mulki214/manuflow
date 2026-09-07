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
import '../quality/quality_page.dart';
import '../receiving/receiving_page.dart';
import '../sales_order/sales_order_page.dart';
import '../users/change_password_dialog.dart';
import '../warehouse/warehouse_page.dart';
import 'production_models.dart';
import 'consumable_disposition_dialog.dart';
import 'production_page.dart';
import 'wip_execution_form_dialog.dart';

enum _WipView { queue, history }

class WipProductionPage extends StatefulWidget {
  const WipProductionPage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<WipProductionPage> createState() => _WipProductionPageState();
}

class _WipProductionPageState extends State<WipProductionPage> {
  final _search = TextEditingController();
  _WipView _view = _WipView.queue;
  List<ProductionWipJobModel> _jobs = [];
  List<ProductionExecutionModel> _executions = [];
  List<Map<String, dynamic>> _plants = [];
  List<ProductionProcessModel> _processes = [];
  String? _plantCode;
  String? _processCode;
  DateTime? _from;
  DateTime? _to;
  bool _loading = false;
  String? _error;
  int _page = 1;
  int _total = 0;
  final int _size = 10;

  int get _pages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _loadLookups();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _loadLookups() async {
    try {
      final responses = await Future.wait([
        widget.auth.api.getJson('/master-data/plants?page=1&size=100'),
        widget.auth.api.getJson('/production/processes?page=1&size=100'),
      ]);
      if (!mounted) return;
      setState(() {
        _plants = (responses[0]['items'] as List).cast<Map<String, dynamic>>();
        _processes = (responses[1]['items'] as List)
            .map(
              (item) =>
                  ProductionProcessModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
      });
    } on ApiException catch (_) {
      // The page remains usable with text search when optional filters fail.
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
        if (_plantCode != null) 'plant_code=$_plantCode',
        if (_processCode != null) 'process_code=$_processCode',
        if (_view == _WipView.queue) 'active_only=true',
        if (_view == _WipView.history && _from != null)
          'date_from=${_apiDate(_from!)}',
        if (_view == _WipView.history && _to != null)
          'date_to=${_apiDate(_to!)}',
      ].join('&');
      final response = await widget.auth.api.getJson(
        _view == _WipView.queue
            ? '/production/wip-jobs?$query'
            : '/production/executions?$query',
      );
      if (!mounted) return;
      setState(() {
        if (_view == _WipView.queue) {
          _jobs = (response['items'] as List)
              .map(
                (item) => ProductionWipJobModel.fromJson(
                  item as Map<String, dynamic>,
                ),
              )
              .toList();
        } else {
          _executions = (response['items'] as List)
              .map(
                (item) => ProductionExecutionModel.fromJson(
                  item as Map<String, dynamic>,
                ),
              )
              .toList();
        }
        _total = response['total'] as int;
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
      } else if (mounted) {
        setState(() => _error = exception.message);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _complete(ProductionWipJobModel job) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => WipExecutionFormDialog(api: widget.auth.api, job: job),
    );
    if (changed == true) {
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('WIP Production result recorded.')),
        );
      }
    }
  }

  Future<void> _scanWipJob() async {
    final scans = await scanProducts(context, widget.auth.api);
    if (scans == null || scans.isEmpty) return;
    final scan = scans.first;
    final job = _jobs
        .where(
          (item) =>
              item.productCode == scan.productCode &&
              (scan.lotNumber == null || item.lotNumber == scan.lotNumber),
        )
        .firstOrNull;
    if (job == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'No matching WIP job is available for the scanned product / lot.',
            ),
          ),
        );
      }
      return;
    }
    await _complete(job);
  }

  Future<void> _reverse(ProductionExecutionModel execution) async {
    final reason = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reverse Production Execution?'),
        content: TextField(
          controller: reason,
          minLines: 3,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: 'Reason *',
            helperText: 'The source WIP will return to the production queue.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Reverse Production'),
          ),
        ],
      ),
    );
    final value = reason.text.trim();
    reason.dispose();
    if (confirmed != true || value.length < 3) return;
    try {
      await widget.auth.api.postJson(
        '/production/executions/${execution.id}/reverse',
        {'reason': value},
      );
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Production execution reversed.')),
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

  Future<void> _pickRange() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2200),
      initialDateRange: _from == null || _to == null
          ? null
          : DateTimeRange(start: _from!, end: _to!),
    );
    if (range != null) {
      setState(() {
        _from = range.start;
        _to = range.end;
        _page = 1;
      });
      _load();
    }
  }

  Future<void> _showStock() async {
    try {
      final result =
          (await widget.auth.api.getJson('/production/stock') as List)
              .cast<Map<String, dynamic>>();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Available Product Stock'),
          content: SizedBox(
            width: 760,
            child: result.isEmpty
                ? const Center(child: Text('No stock available.'))
                : SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: DataTable(
                      columns: const [
                        DataColumn(label: Text('PRODUCT')),
                        DataColumn(label: Text('LOT')),
                        DataColumn(label: Text('QUANTITY')),
                        DataColumn(label: Text('UNIT')),
                        DataColumn(label: Text('LOCATION')),
                      ],
                      rows: result
                          .map(
                            (row) => DataRow(
                              cells: [
                                DataCell(Text(row['product_code'].toString())),
                                DataCell(Text(row['lot_number'].toString())),
                                DataCell(Text(row['quantity'].toString())),
                                DataCell(
                                  Text(
                                    row['unit'].toString() == 'gram'
                                        ? 'grams'
                                        : row['unit'].toString(),
                                  ),
                                ),
                                DataCell(
                                  Text(row['storage_location_code'].toString()),
                                ),
                              ],
                            ),
                          )
                          .toList(),
                    ),
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      );
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(exception.message)));
      }
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
    if (module == AppModule.warehouse && widget.auth.canAccessWarehouse) {
      page = WarehousePage(auth: widget.auth);
    }
    if (module == AppModule.production) {
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
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final desktop = constraints.maxWidth >= 1000;
      final content = _content(desktop);
      if (!desktop) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('WIP Production'),
            actions: [
              if (supportsMobileProductScanner)
                IconButton(
                  tooltip: 'Scan WIP QR',
                  onPressed: _scanWipJob,
                  icon: const Icon(Icons.qr_code_scanner),
                ),
            ],
          ),
          drawer: Drawer(
            child: SafeArea(
              child: AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.production,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.production,
                ),
              ),
            ),
          ),
          body: content,
        );
      }
      return Scaffold(
        body: Row(
          children: [
            AppSidebar(
              auth: widget.auth,
              activeModule: AppModule.production,
              onModuleSelected: (module) => navigateToModule(
                context,
                widget.auth,
                module,
                activeModule: AppModule.production,
              ),
              onChangePassword: () => showDialog<bool>(
                context: context,
                builder: (_) => ChangePasswordDialog(api: widget.auth.api),
              ),
            ),
            Expanded(
              child: Scaffold(
                appBar: AppBar(title: const Text('Production')),
                body: content,
              ),
            ),
          ],
        ),
      );
    },
  );

  Widget _content(bool desktop) => SafeArea(
    child: Padding(
      padding: EdgeInsets.all(desktop ? 32 : 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (desktop)
            Row(
              children: [
                Expanded(child: _titleBlock()),
                _headerActions(),
              ],
            )
          else
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _titleBlock(),
                const SizedBox(height: 12),
                _headerActions(),
              ],
            ),
          const SizedBox(height: 16),
          if (desktop)
            SegmentedButton<_WipView>(
              segments: const [
                ButtonSegment(value: _WipView.queue, icon: Icon(Icons.hourglass_top_outlined), label: Text('WIP Queue')),
                ButtonSegment(value: _WipView.history, icon: Icon(Icons.history), label: Text('Process History')),
              ],
              selected: {_view},
              onSelectionChanged: _changeView,
            )
          else
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SegmentedButton<_WipView>(
                segments: const [
                  ButtonSegment(value: _WipView.queue, icon: Icon(Icons.hourglass_top_outlined), label: Text('WIP Queue')),
                  ButtonSegment(value: _WipView.history, icon: Icon(Icons.history), label: Text('Process History')),
                ],
                selected: {_view},
                onSelectionChanged: _changeView,
              ),
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
                    width: 300,
                    child: TextField(
                      controller: _search,
                      onSubmitted: (_) {
                        _page = 1;
                        _load();
                      },
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search),
                        hintText: 'Search lot, segment, product, or number...',
                        isDense: true,
                      ),
                    ),
                  ),
                  _filterDropdown(
                    'Plant',
                    _plantCode,
                    _plants
                        .map(
                          (item) => MapEntry(
                            item['code'].toString(),
                            '${item['code']} — ${item['name']}',
                          ),
                        )
                        .toList(),
                    (value) {
                      setState(() {
                        _plantCode = value;
                        _page = 1;
                      });
                      _load();
                    },
                  ),
                  _filterDropdown(
                    'Process',
                    _processCode,
                    _processes
                        .map(
                          (item) => MapEntry(
                            item.code,
                            '${item.code} — ${item.name}',
                          ),
                        )
                        .toList(),
                    (value) {
                      setState(() {
                        _processCode = value;
                        _page = 1;
                      });
                      _load();
                    },
                  ),
                  if (_view == _WipView.history)
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
                    onPressed: () {
                      _page = 1;
                      _load();
                    },
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

  Widget _titleBlock() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'WIP Production',
        style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 4),
      Text(
        '$_total ${_view == _WipView.queue ? 'active WIP jobs' : 'production executions'}',
        style: const TextStyle(color: Color(0xFF667085)),
      ),
    ],
  );

  Widget _headerActions() => Wrap(
    spacing: 10,
    runSpacing: 10,
    children: [
      OutlinedButton.icon(onPressed: _showStock, icon: const Icon(Icons.inventory_2_outlined), label: const Text('Check Stock')),
      OutlinedButton.icon(
        onPressed: () => Navigator.of(context).pushReplacement(MaterialPageRoute<void>(builder: (_) => ProductionPage(auth: widget.auth))),
        icon: const Icon(Icons.settings_outlined),
        label: const Text('Process Master'),
      ),
    ],
  );

  void _changeView(Set<_WipView> value) {
    setState(() {
      _view = value.first;
      _page = 1;
      _search.clear();
    });
    _load();
  }

  Widget _filterDropdown(
    String label,
    String? selected,
    List<MapEntry<String, String>> values,
    ValueChanged<String?> onChanged,
  ) => SizedBox(
    width: 200,
    child: DropdownButtonFormField<String?>(
      initialValue: selected,
      decoration: InputDecoration(labelText: label, isDense: true),
      items: [
        const DropdownMenuItem(value: null, child: Text('All')),
        ...values.map(
          (item) => DropdownMenuItem(
            value: item.key,
            child: Text(item.value, overflow: TextOverflow.ellipsis),
          ),
        ),
      ],
      onChanged: onChanged,
    ),
  );

  Widget _body(bool desktop) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    if (_view == _WipView.queue && _jobs.isEmpty) {
      return const Center(
        child: Text(
          'No active WIP Jobs found. Transfer material from Warehouse to a Production Process first.',
        ),
      );
    }
    if (_view == _WipView.history && _executions.isEmpty) {
      return const Center(child: Text('No Production Executions found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() => Card(
    clipBehavior: Clip.antiAlias,
    child: ScrollableDataTable(
      child: _view == _WipView.queue
          ? DataTable(
              columns: const [
                DataColumn(label: Text('LOT / SEGMENT')),
                DataColumn(label: Text('PRODUCT / DESCRIPTION')),
                DataColumn(label: Text('QTY / UNIT')),
                DataColumn(label: Text('PLANT')),
                DataColumn(label: Text('CURRENT PROCESS')),
                DataColumn(label: Text('SOURCE')),
                DataColumn(label: Text('STATUS')),
                DataColumn(label: Text('ACTION')),
              ],
              rows: _jobs
                  .map(
                    (job) => DataRow(
                      cells: [
                        DataCell(Text('${job.lotNumber}\n${job.segmentCode}')),
                        DataCell(
                          SizedBox(
                            width: 230,
                            child: Text(
                              '${job.productCode} — ${job.description}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                        DataCell(
                          Text(
                            '${_number(job.currentQuantity)} ${unitLabel(job.unit)}',
                          ),
                        ),
                        DataCell(Text(job.plantName)),
                        DataCell(
                          Text('${job.processCode} — ${job.processName}'),
                        ),
                        DataCell(Text(job.sourceTransferNumber)),
                        DataCell(_jobStatus(job.status)),
                        DataCell(
                          FilledButton(
                            onPressed: job.canComplete
                                ? () => _complete(job)
                                : null,
                            child: const Text('Process'),
                          ),
                        ),
                      ],
                    ),
                  )
                  .toList(),
            )
          : DataTable(
              columns: const [
                DataColumn(label: Text('DATE')),
                DataColumn(label: Text('NUMBER')),
                DataColumn(label: Text('SHIFT')),
                DataColumn(label: Text('DESCRIPTION / LOT')),
                DataColumn(label: Text('QTY / UNIT')),
                DataColumn(label: Text('PLANT')),
                DataColumn(label: Text('BEFORE')),
                DataColumn(label: Text('AFTER')),
                DataColumn(label: Text('MACHINE')),
                DataColumn(label: Text('GOOD / REPAIR / NG')),
                DataColumn(label: Text('ACTION')),
              ],
              rows: _executions
                  .map(
                    (item) => DataRow(
                      onSelectChanged: (_) => _executionDetail(item),
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
                        DataCell(Text(item.shift)),
                        DataCell(
                          SizedBox(
                            width: 220,
                            child: Text(
                              '${item.description}\nLot ${item.lotNumber}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                        DataCell(
                          Text(
                            '${_number(item.processingQuantity)} ${unitLabel(item.unit)}',
                          ),
                        ),
                        DataCell(Text(item.plantName)),
                        DataCell(Text(item.beforeProcess)),
                        DataCell(Text(item.afterProcess)),
                        DataCell(Text(item.machineName)),
                        DataCell(
                          Text(
                            '${_number(item.goodQuantity)} / ${_number(item.repairQuantity)} / ${_number(item.ngQuantity)}',
                          ),
                        ),
                        DataCell(
                          item.canReverse
                              ? OutlinedButton(
                                  onPressed: () => _reverse(item),
                                  child: const Text('Reverse'),
                                )
                              : const Text('-'),
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
    itemCount: _view == _WipView.queue ? _jobs.length : _executions.length,
    separatorBuilder: (_, _) => const SizedBox(height: 10),
    itemBuilder: (context, index) {
      if (_view == _WipView.queue) {
        final job = _jobs[index];
        return Card(
          child: ListTile(
            onTap: job.canComplete ? () => _complete(job) : null,
            title: Text('${job.processCode} — ${job.processName}'),
            subtitle: Text(
              '${job.description}\nLot ${job.lotNumber} • ${_number(job.currentQuantity)} ${unitLabel(job.unit)}\n${job.plantName}',
            ),
            isThreeLine: true,
            trailing: _jobStatus(job.status),
          ),
        );
      }
      final item = _executions[index];
      return Card(
        child: ListTile(
          onTap: () => _executionDetail(item),
          title: Text(item.number),
          subtitle: Text(
            '${item.description}\n${item.beforeProcess} → ${item.afterProcess}\nGood ${_number(item.goodQuantity)} • Repair ${_number(item.repairQuantity)} • NG ${_number(item.ngQuantity)}',
          ),
          isThreeLine: true,
          trailing: item.canReverse
              ? OutlinedButton(
                  onPressed: () => _reverse(item),
                  child: const Text('Reverse'),
                )
              : null,
        ),
      );
    },
  );

  void _executionDetail(ProductionExecutionModel item) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(item.number),
        content: SizedBox(
          width: 620,
          child: Wrap(
            spacing: 24,
            runSpacing: 16,
            children: [
              _detail('Date', _date(item.date)),
              _detail('Shift', item.shift),
              _detail(
                'Lot / Segment',
                '${item.lotNumber}\n${item.segmentCode}',
              ),
              _detail('Before Process', item.beforeProcess),
              _detail('After Process', item.afterProcess),
              _detail('Machine', item.machineName),
              _detail(
                'Processed',
                '${_number(item.processingQuantity)} ${unitLabel(item.unit)}',
              ),
              _detail(
                'Good',
                '${_number(item.goodQuantity)} ${unitLabel(item.unit)}',
              ),
              _detail(
                'Repair',
                '${_number(item.repairQuantity)} ${unitLabel(item.unit)}',
              ),
              _detail(
                'NG',
                '${_number(item.ngQuantity)} ${unitLabel(item.unit)}',
              ),
              _detail(
                'Time Range',
                item.startedAt == null || item.endedAt == null
                    ? '-'
                    : '${item.startedAt!.toLocal()}\n${item.endedAt!.toLocal()}',
              ),
              _detail('Break', '${item.breakDurationMinutes} minutes'),
              _detail(
                'Calculated Cycle Time',
                item.cycleTimeSeconds == null
                    ? '-'
                    : '${_number(item.cycleTimeSeconds!)} seconds',
              ),
              _detail(
                'Observed Cycle Time',
                item.observedCycleTimeSeconds == null
                    ? '-'
                    : '${_number(item.observedCycleTimeSeconds!)} seconds',
              ),
              _detail(
                'NG Control',
                item.ngLimitExceeded
                    ? 'Head override: ${item.ngOverrideReason ?? '-'}'
                    : 'Within limit',
              ),
              _detail('Performed By', item.performedBy),
            ],
          ),
        ),
        actions: [
          OutlinedButton.icon(
            onPressed: () async {
              Navigator.pop(context);
              await showDialog<bool>(
                context: this.context,
                barrierDismissible: false,
                builder: (_) => ConsumableDispositionDialog(
                  api: widget.auth.api,
                  executionId: item.id,
                ),
              );
            },
            icon: const Icon(Icons.recycling_outlined),
            label: const Text('Consumables'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _detail(String label, String value) => SizedBox(
    width: 180,
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

  Widget _jobStatus(String value) => Chip(
    visualDensity: VisualDensity.compact,
    label: Text(value.replaceAll('_', ' ').toUpperCase()),
  );
}

String _apiDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
String _date(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
String _number(double value) => value == value.roundToDouble()
    ? value.toInt().toString()
    : value
          .toStringAsFixed(3)
          .replaceFirst(RegExp(r'0+$'), '')
          .replaceFirst(RegExp(r'\.$'), '');
