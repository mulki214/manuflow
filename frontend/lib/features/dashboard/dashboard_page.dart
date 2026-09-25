import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../auth/auth_controller.dart';

double _dashboardNumber(Object? value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? 0;
  return 0;
}

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  Map<String, dynamic>? _data;
  String? _error;
  late DateTimeRange _performanceRange;

  @override
  void initState() {
    super.initState();
    final today = DateUtils.dateOnly(DateTime.now());
    _performanceRange = DateTimeRange(
      start: today.subtract(const Duration(days: 6)),
      end: today,
    );
    _load();
  }

  Future<void> _load() async {
    try {
      final value = await widget.auth.api.getJson(
        '/dashboard?from_date=${_dateValue(_performanceRange.start)}'
        '&to_date=${_dateValue(_performanceRange.end)}',
      );
      if (mounted) setState(() => _data = value);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  String _dateValue(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

  Future<void> _pickPerformanceRange() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateUtils.dateOnly(DateTime.now()),
      initialDateRange: _performanceRange,
      helpText: 'Performance period (maximum 7 days)',
    );
    if (range == null || !mounted) return;
    if (range.duration.inDays > 6) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Performance period can be at most 7 days.'),
        ),
      );
      return;
    }
    setState(() => _performanceRange = range);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final sales = data?['sales_orders'] as Map<String, dynamic>?;
    final wip = data?['wip'] as Map<String, dynamic>?;
    final performance =
        data?['production_performance'] as Map<String, dynamic>?;
    return AppModuleScaffold(
      auth: widget.auth,
      activeModule: AppModule.dashboard,
      title: 'Dashboard',
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: _error != null
            ? Center(child: Text(_error!))
            : data == null
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.only(bottom: 24),
                  children: [
                    Text(
                      'Operational Dashboard',
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Live overview from Sales Order through Delivery.',
                      style: TextStyle(color: Color(0xFF667085)),
                    ),
                    const SizedBox(height: 24),
                    GridView.count(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisCount: MediaQuery.sizeOf(context).width >= 700
                          ? 3
                          : 2,
                      crossAxisSpacing: 14,
                      mainAxisSpacing: 14,
                      childAspectRatio: MediaQuery.sizeOf(context).width >= 700
                          ? 1.7
                          : 1.15,
                      children: [
                        _KpiCard('Open Sales Orders', sales?['open']),
                        _KpiCard('Production WIP', wip?['production']),
                        _KpiCard('Awaiting QC', wip?['quality']),
                        _KpiCard(
                          'Awaiting Finish Good',
                          wip?['finish_good_queue'],
                        ),
                        _KpiCard('Finish Good Postings', data['finish_goods']),
                        _KpiCard('Deliveries', data['deliveries']),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'OP Cycle Time Performance',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Actual cycle time compared with the target set per product and OP.',
                      style: TextStyle(color: Color(0xFF667085)),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _pickPerformanceRange,
                      icon: const Icon(Icons.date_range_outlined),
                      label: Text(
                        '${_dateValue(_performanceRange.start)} – ${_dateValue(_performanceRange.end)}',
                      ),
                    ),
                    const SizedBox(height: 12),
                    _OpPerformanceBarChart(
                      items: (performance?['items'] as List? ?? const [])
                          .cast<Map<String, dynamic>>(),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'WIP Status Distribution',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _WipPieChart(
                      values: {
                        'Production': _dashboardNumber(wip?['production']),
                        'QC': _dashboardNumber(wip?['quality']),
                        'Finish Good': _dashboardNumber(
                          wip?['finish_good_queue'],
                        ),
                        'NG': _dashboardNumber(wip?['ng']),
                      },
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _OpPerformanceBarChart extends StatelessWidget {
  const _OpPerformanceBarChart({required this.items});
  final List<Map<String, dynamic>> items;
  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text(
            'No completed production execution with a cycle-time target in this period.',
          ),
        ),
      );
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: items.map((item) {
            final performance = _dashboardNumber(item['performance_percent']);
            final color = performance >= 100
                ? const Color(0xFF12B76A)
                : performance >= 85
                ? const Color(0xFFFDB022)
                : const Color(0xFFF04438);
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${item['product_code']} / ${item['process_code']}',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Expanded(
                        child: LinearProgressIndicator(
                          value: performance.clamp(0, 100).toDouble() / 100,
                          minHeight: 18,
                          color: color,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      const SizedBox(width: 10),
                      SizedBox(
                        width: 62,
                        child: Text(
                          '${performance.toStringAsFixed(1)}%',
                          textAlign: TextAlign.right,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Target ${_seconds(item['target_cycle_time_seconds'])} s · '
                    'Actual ${_seconds(item['actual_cycle_time_seconds'])} s · '
                    '${item['execution_count']} execution(s)',
                    style: const TextStyle(
                      color: Color(0xFF667085),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  String _seconds(Object? value) => _dashboardNumber(value).toStringAsFixed(2);
}

class _WipPieChart extends StatelessWidget {
  const _WipPieChart({required this.values});
  final Map<String, double> values;
  @override
  Widget build(BuildContext context) {
    const colors = [
      Color(0xFF155EEF),
      Color(0xFF12B76A),
      Color(0xFFFDB022),
      Color(0xFFF04438),
    ];
    final entries = values.entries.toList();
    final total = values.values.fold(0.0, (sum, value) => sum + value);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            SizedBox(
              width: 150,
              height: 150,
              child: CustomPaint(
                painter: _PiePainter(
                  entries.map((entry) => entry.value).toList(),
                  colors,
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                children: List.generate(entries.length, (index) {
                  final entry = entries[index];
                  final percent = total == 0
                      ? ''
                      : ' (${(entry.value / total * 100).toStringAsFixed(0)}%)';
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      children: [
                        Container(width: 12, height: 12, color: colors[index]),
                        const SizedBox(width: 8),
                        Expanded(child: Text(entry.key)),
                        Text('${entry.value.toInt()}$percent'),
                      ],
                    ),
                  );
                }),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PiePainter extends CustomPainter {
  const _PiePainter(this.values, this.colors);
  final List<double> values;
  final List<Color> colors;
  @override
  void paint(Canvas canvas, Size size) {
    final total = values.fold(0.0, (sum, value) => sum + value);
    var start = -1.5708;
    final rect = Offset.zero & size;
    for (var index = 0; index < values.length; index++) {
      final sweep = total == 0 ? 0.0 : values[index] / total * 6.28318;
      canvas.drawArc(rect, start, sweep, true, Paint()..color = colors[index]);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _PiePainter oldDelegate) =>
      oldDelegate.values != values;
}

class _KpiCard extends StatelessWidget {
  const _KpiCard(this.label, this.value);
  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF667085))),
          const SizedBox(height: 16),
          const Spacer(),
          Text(
            '${value ?? 0}',
            style: Theme.of(
              context,
            ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    ),
  );
}
