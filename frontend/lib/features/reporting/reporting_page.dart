import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/crud_widgets.dart';
import '../auth/auth_controller.dart';

class ReportingPage extends StatefulWidget {
  const ReportingPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<ReportingPage> createState() => _ReportingPageState();
}

class _ReportingPageState extends State<ReportingPage> {
  static const _reports = {
    'stock': 'Stock by Lot',
    'purchase-order': 'Purchase Order Outstanding',
    'sales-order-fulfillment': 'Sales Order Fulfillment',
    'production': 'Production',
    'quality': 'Quality Control',
    'machine': 'Machine Performance',
    'operator': 'Operator Performance',
  };
  String _report = 'stock';
  List<Map<String, dynamic>> _rows = [];
  bool _loading = true;
  String? _error;
  DateTime? _dateFrom;
  DateTime? _dateTo;

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _date(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

  String get _query {
    final values = [
      if (_dateFrom != null) 'date_from=${_date(_dateFrom!)}',
      if (_dateTo != null) 'date_to=${_date(_dateTo!)}',
    ];
    return values.isEmpty ? '' : '?${values.join('&')}';
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await widget.auth.api.getJson(
        '/reporting/$_report$_query',
      );
      if (mounted) {
        setState(() => _rows = (response as List).cast<Map<String, dynamic>>());
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _selectDate(bool start) async {
    final selected = await showDatePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
      initialDate: (start ? _dateFrom : _dateTo) ?? DateTime.now(),
    );
    if (selected == null) return;
    setState(() {
      if (start) {
        _dateFrom = selected;
      } else {
        _dateTo = selected;
      }
    });
    await _load();
  }

  Future<void> _export() async {
    try {
      final bytes = await widget.auth.api.getBytes(
        '/reporting/$_report/export-excel$_query',
      );
      await FileSaver.instance.saveFile(
        name: _report,
        bytes: bytes,
        fileExtension: 'xlsx',
        mimeType: MimeType.microsoftExcel,
      );
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.reporting,
    title: 'Reporting',
    actions: [
      IconButton(
        onPressed: _export,
        tooltip: 'Download Excel',
        icon: const Icon(Icons.download_outlined),
      ),
      IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
    ],
    body: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Reporting',
            style: Theme.of(
              context,
            ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Wrap(
                spacing: 12,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 280,
                    child: DropdownButtonFormField<String>(
                      initialValue: _report,
                      decoration: const InputDecoration(labelText: 'Report'),
                      items: _reports.entries
                          .map(
                            (entry) => DropdownMenuItem(
                              value: entry.key,
                              child: Text(entry.value),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => _report = value);
                        _load();
                      },
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _selectDate(true),
                    icon: const Icon(Icons.date_range_outlined),
                    label: Text(
                      _dateFrom == null ? 'Date From' : _date(_dateFrom!),
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _selectDate(false),
                    icon: const Icon(Icons.event_outlined),
                    label: Text(_dateTo == null ? 'Date To' : _date(_dateTo!)),
                  ),
                  FilledButton.icon(
                    onPressed: _export,
                    icon: const Icon(Icons.download),
                    label: const Text('Download Excel'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Expanded(child: _body()),
        ],
      ),
    ),
  );

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    if (_rows.isEmpty) {
      return Center(child: Text('No ${_reports[_report]} records found.'));
    }
    final columns = _rows.first.keys.toList();
    return Card(
      clipBehavior: Clip.antiAlias,
      child: ScrollableDataTable(
        child: DataTable(
          columns: columns
              .map(
                (name) => DataColumn(
                  label: Text(name.replaceAll('_', ' ').toUpperCase()),
                ),
              )
              .toList(),
          rows: _rows
              .map(
                (row) => DataRow(
                  cells: columns
                      .map(
                        (name) => DataCell(Text(row[name]?.toString() ?? '-')),
                      )
                      .toList(),
                ),
              )
              .toList(),
        ),
      ),
    );
  }
}
