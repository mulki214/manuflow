import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/crud_widgets.dart';
import '../../shared/mobile_product_scanner.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';
import '../master_data/master_data_page.dart';
import '../production/production_page.dart';
import '../users/user_page.dart';
import 'quality_inspection_form_dialog.dart';
import 'quality_models.dart';

enum _QualityView { queue, history }

class QualityPage extends StatefulWidget {
  const QualityPage({super.key, required this.auth});
  final AuthController auth;
  @override
  State<QualityPage> createState() => _QualityPageState();
}

class _QualityPageState extends State<QualityPage> {
  final _search = TextEditingController();
  _QualityView _view = _QualityView.queue;
  List<QualityWipJobModel> _jobs = [];
  List<QualityInspectionModel> _inspections = [];
  List<Map<String, dynamic>> _plants = [];
  String? _plant;
  DateTime? _from, _to;
  bool _loading = false;
  String? _error;
  int _page = 1, _total = 0;
  static const _size = 10;
  int get _pages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _loadPlants();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  String _date(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  String _number(double value) => value == value.roundToDouble()
      ? value.toInt().toString()
      : value.toString();

  Future<void> _loadPlants() async {
    try {
      final data = await widget.auth.api.getJson(
        '/master-data/plants?page=1&size=100',
      );
      if (mounted) {
        setState(
          () => _plants = (data['items'] as List).cast<Map<String, dynamic>>(),
        );
      }
    } catch (_) {}
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final q = [
        'page=$_page',
        'size=$_size',
        if (_search.text.trim().isNotEmpty)
          'search=${Uri.encodeQueryComponent(_search.text.trim())}',
        if (_plant != null) 'plant_code=$_plant',
        if (_view == _QualityView.history && _from != null)
          'date_from=${_date(_from!)}',
        if (_view == _QualityView.history && _to != null)
          'date_to=${_date(_to!)}',
      ].join('&');
      final data = await widget.auth.api.getJson(
        _view == _QualityView.queue
            ? '/quality/wip-jobs?$q'
            : '/quality/inspections?$q',
      );
      if (!mounted) return;
      setState(() {
        _total = data['total'] as int;
        if (_view == _QualityView.queue) {
          _jobs = (data['items'] as List)
              .map(
                (v) => QualityWipJobModel.fromJson(v as Map<String, dynamic>),
              )
              .toList();
        } else {
          _inspections = (data['items'] as List)
              .map(
                (v) =>
                    QualityInspectionModel.fromJson(v as Map<String, dynamic>),
              )
              .toList();
        }
      });
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await widget.auth.logout();
      } else if (mounted) {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _inspect(QualityWipJobModel job) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          QualityInspectionFormDialog(api: widget.auth.api, job: job),
    );
    if (changed == true) {
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Quality inspection recorded.')),
        );
      }
    }
  }

  Future<void> _scanQualityJob() async {
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
              'No matching Quality Queue job is available for the scanned product / lot.',
            ),
          ),
        );
      }
      return;
    }
    await _inspect(job);
  }

  Future<void> _reverse(QualityInspectionModel inspection) async {
    final reason = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reverse Quality Inspection?'),
        content: TextField(
          controller: reason,
          minLines: 3,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: 'Reason *',
            helperText: 'The lot will return to the QC queue.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Reverse QC'),
          ),
        ],
      ),
    );
    final value = reason.text.trim();
    reason.dispose();
    if (confirmed != true || value.length < 3) return;
    try {
      await widget.auth.api.postJson(
        '/quality/inspections/${inspection.id}/reverse',
        {'reason': value},
      );
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Quality inspection reversed.')),
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

  // ignore: unused_element
  void _module(AppModule module) {
    Widget? target;
    if (module == AppModule.user) {
      target = UserPage(auth: widget.auth);
    }
    if (module == AppModule.masterData) {
      target = MasterDataPage(auth: widget.auth);
    }
    if (module == AppModule.production) {
      target = ProductionPage(auth: widget.auth);
    }
    if (target != null) {
      Navigator.of(
        context,
      ).pushReplacement(MaterialPageRoute<void>(builder: (_) => target!));
    }
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) => AppModuleScaffold(
      auth: widget.auth,
      activeModule: AppModule.quality,
      title: 'Quality',
      actions: [
        if (supportsMobileProductScanner)
          IconButton(
            tooltip: 'Scan QC QR',
            onPressed: _scanQualityJob,
            icon: const Icon(Icons.qr_code_scanner),
          ),
        IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
      ],
      body: _content(constraints.maxWidth >= 1000),
    ),
  );

  Widget _content(bool desktop) => Padding(
    padding: EdgeInsets.all(desktop ? 40 : 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Quality',
          style: Theme.of(
            context,
          ).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 6),
        Text(
          _view == _QualityView.queue
              ? '$_total lots awaiting Quality inspection'
              : '$_total quality inspection records',
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(color: const Color(0xFF667085)),
        ),
        const SizedBox(height: 24),
        SegmentedButton<_QualityView>(
          segments: const [
            ButtonSegment(
              value: _QualityView.queue,
              label: Text('QC Queue'),
              icon: Icon(Icons.pending_actions_outlined),
            ),
            ButtonSegment(
              value: _QualityView.history,
              label: Text('Inspection History'),
              icon: Icon(Icons.history_outlined),
            ),
          ],
          selected: {_view},
          onSelectionChanged: (v) {
            setState(() {
              _view = v.first;
              _page = 1;
            });
            _load();
          },
        ),
        const SizedBox(height: 18),
        _filters(desktop),
        const SizedBox(height: 18),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
              ? Center(child: Text(_error!))
              : _view == _QualityView.queue
              ? _queue(desktop)
              : _history(desktop),
        ),
        _pagination(),
      ],
    ),
  );
  Widget _filters(bool desktop) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          SizedBox(
            width: desktop ? 450 : double.infinity,
            child: TextField(
              controller: _search,
              onSubmitted: (_) {
                setState(() => _page = 1);
                _load();
              },
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Search product, lot, quality number, or problem',
              ),
            ),
          ),
          SizedBox(
            width: 220,
            child: DropdownButtonFormField<String>(
              initialValue: _plant,
              decoration: const InputDecoration(labelText: 'Plant'),
              items: [
                const DropdownMenuItem(value: null, child: Text('All plants')),
                ..._plants.map(
                  (p) => DropdownMenuItem(
                    value: p['code'].toString(),
                    child: Text('${p['code']} — ${p['name']}'),
                  ),
                ),
              ],
              onChanged: (v) {
                setState(() {
                  _plant = v;
                  _page = 1;
                });
                _load();
              },
            ),
          ),
          if (_view == _QualityView.history)
            OutlinedButton.icon(
              onPressed: _pickRange,
              icon: const Icon(Icons.date_range_outlined),
              label: Text(
                _from == null
                    ? 'Date Range'
                    : '${_date(_from!)} – ${_date(_to!)}',
              ),
            ),
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ],
      ),
    ),
  );
  Widget _queue(bool desktop) {
    if (_jobs.isEmpty) {
      return const Center(
        child: Text('No lots are waiting for Quality inspection.'),
      );
    }
    if (!desktop) {
      return ListView.separated(
        itemCount: _jobs.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) {
          final job = _jobs[i];
          return Card(
            child: ListTile(
              title: Text('${job.productCode} — ${job.description}'),
              subtitle: Text(
                'Lot ${job.lotNumber} • ${_number(job.quantity)} ${unitLabel(job.unit)}\n${job.plantName} • ${job.beforeProcess}',
              ),
              isThreeLine: true,
              trailing: FilledButton(
                onPressed: () => _inspect(job),
                child: const Text('Inspect'),
              ),
            ),
          );
        },
      );
    }
    return ScrollableDataTable(
      child: DataTable(
        columns: const [
          DataColumn(label: Text('PRODUCT')),
          DataColumn(label: Text('LOT')),
          DataColumn(label: Text('QTY')),
          DataColumn(label: Text('UNIT')),
          DataColumn(label: Text('PLANT')),
          DataColumn(label: Text('BEFORE PROCESS')),
          DataColumn(label: Text('ACTION')),
        ],
        rows: _jobs
            .map(
              (job) => DataRow(
                cells: [
                  DataCell(Text(job.description)),
                  DataCell(Text(job.lotNumber)),
                  DataCell(Text(_number(job.quantity))),
                  DataCell(Text(unitLabel(job.unit))),
                  DataCell(Text(job.plantName)),
                  DataCell(Text(job.beforeProcess)),
                  DataCell(
                    FilledButton(
                      onPressed: () => _inspect(job),
                      child: const Text('Inspect'),
                    ),
                  ),
                ],
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _history(bool desktop) {
    if (_inspections.isEmpty) {
      return const Center(child: Text('No Quality inspections found.'));
    }
    if (!desktop) {
      return ListView.separated(
        itemCount: _inspections.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (_, i) {
          final item = _inspections[i];
          return Card(
            child: ListTile(
              title: Text('${item.number} — ${item.description}'),
              subtitle: Text(
                '${_date(item.date)} • ${item.shift}\nLot ${item.lotNumber} • Pass ${_number(item.pass)}, Repair ${_number(item.repair)}, NG ${_number(item.ng)}\n${item.problem.isEmpty ? 'No problem recorded' : item.problem}',
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
    }
    return ScrollableDataTable(
      child: DataTable(
        columns: const [
          DataColumn(label: Text('NO')),
          DataColumn(label: Text('DATE')),
          DataColumn(label: Text('SHIFT')),
          DataColumn(label: Text('DESCRIPTION')),
          DataColumn(label: Text('LOT')),
          DataColumn(label: Text('QTY')),
          DataColumn(label: Text('UNIT')),
          DataColumn(label: Text('PLANT')),
          DataColumn(label: Text('BEFORE PROCESS')),
          DataColumn(label: Text('AFTER PROCESS')),
          DataColumn(label: Text('PROBLEM')),
          DataColumn(label: Text('ACTION')),
        ],
        rows: _inspections
            .map(
              (item) => DataRow(
                cells: [
                  DataCell(Text(item.number)),
                  DataCell(Text(_date(item.date))),
                  DataCell(Text(item.shift)),
                  DataCell(Text(item.description)),
                  DataCell(Text(item.lotNumber)),
                  DataCell(Text(_number(item.quantity))),
                  DataCell(Text(unitLabel(item.unit))),
                  DataCell(Text(item.plantName)),
                  DataCell(Text(item.beforeProcess)),
                  DataCell(
                    Text(
                      item.repair > 0
                          ? 'Repair: ${item.repairProcess ?? '-'}'
                          : item.ng > 0 && item.pass == 0
                          ? 'NG'
                          : item.isReversed
                          ? 'Reversed'
                          : 'Finish Goods',
                    ),
                  ),
                  DataCell(Text(item.problem)),
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
    );
  }

  Widget _pagination() => Padding(
    padding: const EdgeInsets.only(top: 12),
    child: Row(
      children: [
        Text(
          'Page $_page of $_pages • $_total records',
          style: const TextStyle(color: Color(0xFF667085)),
        ),
        const Spacer(),
        IconButton(
          onPressed: _page <= 1
              ? null
              : () {
                  setState(() => _page--);
                  _load();
                },
          icon: const Icon(Icons.chevron_left),
        ),
        IconButton(
          onPressed: _page >= _pages
              ? null
              : () {
                  setState(() => _page++);
                  _load();
                },
          icon: const Icon(Icons.chevron_right),
        ),
      ],
    ),
  );
}
