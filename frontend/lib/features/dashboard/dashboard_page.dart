import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../auth/auth_controller.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  Map<String, dynamic>? _data;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final value = await widget.auth.api.getJson('/dashboard');
      if (mounted) setState(() => _data = value);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final sales = data?['sales_orders'] as Map<String, dynamic>?;
    final wip = data?['wip'] as Map<String, dynamic>?;
    return AppModuleScaffold(
      auth: widget.auth,
      activeModule: AppModule.dashboard,
      title: 'Dashboard',
      actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))],
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: _error != null
            ? Center(child: Text(_error!))
            : data == null
            ? const Center(child: CircularProgressIndicator())
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Operational Dashboard',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Live overview from Sales Order through Delivery.',
                    style: TextStyle(color: Color(0xFF667085)),
                  ),
                  const SizedBox(height: 24),
                  Expanded(
                    child: GridView.count(
                      crossAxisCount: MediaQuery.sizeOf(context).width >= 700
                          ? 3
                          : 2,
                      crossAxisSpacing: 14,
                      mainAxisSpacing: 14,
                      childAspectRatio: 1.7,
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
                  ),
                ],
              ),
      ),
    );
  }
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
