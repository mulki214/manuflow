import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/modal_widgets.dart';
import '../auth/auth_controller.dart';
import '../users/change_password_dialog.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  List<Map<String, dynamic>> _records = [];
  bool _loading = false;
  String? _error;
  bool get _isAdmin => widget.auth.currentUser?.accessLevel == 'administrator';

  @override
  void initState() {
    super.initState();
    if (_isAdmin) _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.auth.api.getJson('/settings/stock-rebalancing?size=100');
      if (mounted) setState(() { _records = (data['items'] as List).cast<Map<String, dynamic>>(); _error = null; });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _changePassword() async {
    final changed = await showDialog<bool>(context: context, builder: (_) => ChangePasswordDialog(api: widget.auth.api));
    if (changed == true && mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Password updated')));
  }

  Future<void> _create() async {
    final lotsJson = await widget.auth.api.getJson('/settings/stock-rebalancing/lots?limit=500');
    if (!mounted) return;
    final lots = (lotsJson as List).cast<Map<String, dynamic>>();
    final saved = await showDialog<bool>(context: context, builder: (_) => _RebalanceDialog(api: widget.auth.api, lots: lots));
    if (saved == true) _load();
  }

  void _detail(Map<String, dynamic> record) => showDialog<void>(context: context, builder: (_) => AlertDialog(
    title: CopyableCodeText(record['rebalance_number'].toString(), style: Theme.of(context).textTheme.titleLarge),
    content: SizedBox(width: 820, child: ModalScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
      DetailValue(label: 'Date', value: record['rebalance_date'].toString()),
      DetailValue(label: 'Posted by', value: record['created_by_name'].toString()),
      DetailValue(label: 'Notes', value: record['notes'].toString()),
      const SizedBox(height: 12),
      ModalHorizontalScroll(child: DataTable(columns: const [DataColumn(label: Text('Product / Lot')), DataColumn(label: Text('System')), DataColumn(label: Text('Physical')), DataColumn(label: Text('Difference')), DataColumn(label: Text('Reason'))], rows: (record['lines'] as List).cast<Map<String,dynamic>>().map((line) => DataRow(cells: [DataCell(Text('${line['product_name']}\n${line['lot_number']}')), DataCell(Text('${line['system_quantity']} ${line['unit']}')), DataCell(Text('${line['physical_quantity']} ${line['unit']}')), DataCell(Text('${line['difference_quantity']} ${line['unit']}')), DataCell(Text(line['reason'].toString()))])).toList())),
    ]))),
    actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
  ));

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth, activeModule: AppModule.settings, title: 'Settings',
    floatingActionButton: _isAdmin ? FloatingActionButton.extended(onPressed: _create, icon: const Icon(Icons.tune), label: const Text('Rebalance Stock')) : null,
    body: RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(24), children: [
      Text('Settings', style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 6),
      const Text('Manage your account and inventory controls.'), const SizedBox(height: 24),
      Card(child: ListTile(leading: const Icon(Icons.password_outlined), title: const Text('Change Password'), subtitle: const Text('Update the password for your account.'), trailing: const Icon(Icons.chevron_right), onTap: _changePassword)),
      if (_isAdmin) ...[
        const SizedBox(height: 28), Text('Inventory Control', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 6), const Text('Posted rebalancing documents are immutable and recorded in the inventory audit trail.'), const SizedBox(height: 12),
        if (_loading) const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
        else if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))
        else if (_records.isEmpty) const Card(child: Padding(padding: EdgeInsets.all(28), child: Text('No stock rebalancing records yet.')))
        else ..._records.map((item) => Card(child: ListTile(title: CopyableCodeText(item['rebalance_number'].toString()), subtitle: Text('${item['rebalance_date']} • ${item['created_by_name']} • ${(item['lines'] as List).length} line(s)'), trailing: const Icon(Icons.chevron_right), onTap: () => _detail(item)))),
      ],
    ])),
  );
}

class _RebalanceLine { int? lotId; final physical = TextEditingController(); final reason = TextEditingController(); final notes = TextEditingController(); void dispose() { physical.dispose(); reason.dispose(); notes.dispose(); } }

class _RebalanceDialog extends StatefulWidget { const _RebalanceDialog({required this.api, required this.lots}); final ApiClient api; final List<Map<String,dynamic>> lots; @override State<_RebalanceDialog> createState() => _RebalanceDialogState(); }
class _RebalanceDialogState extends State<_RebalanceDialog> {
  final _form = GlobalKey<FormState>(); final _notes = TextEditingController(); final _lines = [_RebalanceLine()]; bool _saving = false; String? _error;
  @override void dispose() { _notes.dispose(); for (final line in _lines) { line.dispose(); } super.dispose(); }
  Map<String,dynamic>? _lot(int? id) => id == null ? null : widget.lots.cast<Map<String,dynamic>?>().firstWhere((item) => item?['id'] == id, orElse: () => null);
  Future<void> _save() async { if (!_form.currentState!.validate()) return; setState(() { _saving = true; _error = null; }); try { await widget.api.postJson('/settings/stock-rebalancing', {'rebalance_date': DateTime.now().toIso8601String().substring(0,10), 'notes': _notes.text, 'lines': _lines.map((line) => {'lot_id': line.lotId, 'physical_quantity': line.physical.text, 'reason': line.reason.text, 'notes': line.notes.text}).toList()}); if (mounted) Navigator.pop(context, true); } on ApiException catch (e) { if (mounted) setState(() => _error = e.message); } finally { if (mounted) setState(() => _saving = false); } }
  @override Widget build(BuildContext context) => AlertDialog(title: const Text('Rebalance Stock'), content: SizedBox(width: 760, child: ModalScrollView(child: Form(key: _form, child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [const Text('Count the physical quantity for each selected lot. The difference is posted immediately and cannot be edited.'), const SizedBox(height: 12), ..._lines.asMap().entries.map((entry) { final i=entry.key; final line=entry.value; final lot=_lot(line.lotId); return Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(children:[Row(children:[Text('Line ${i+1}', style: const TextStyle(fontWeight: FontWeight.bold)), const Spacer(), if (_lines.length>1) IconButton(onPressed:()=>setState((){line.dispose();_lines.removeAt(i);}), icon: const Icon(Icons.delete_outline))]), DropdownButtonFormField<int>(initialValue: line.lotId, isExpanded:true, decoration: const InputDecoration(labelText:'Product Lot *'), items: widget.lots.map((l)=>DropdownMenuItem(value:l['id'] as int, child: Text('${l['product_name']} — Lot ${l['lot_number']} — ${l['current_quantity']} ${l['unit']}', overflow: TextOverflow.ellipsis))).toList(), onChanged:(v)=>setState(()=>line.lotId=v), validator:(v)=>v==null?'Select a product lot':null), if(lot!=null) Align(alignment: Alignment.centerLeft, child: Padding(padding:const EdgeInsets.only(top:8), child:Text('System quantity: ${lot['current_quantity']} ${lot['unit']} • ${lot['storage_location_code']}'))), const SizedBox(height:8), Row(children:[Expanded(child:TextFormField(controller:line.physical, keyboardType: const TextInputType.numberWithOptions(decimal:true), decoration: const InputDecoration(labelText:'Physical Quantity *'), validator:(v)=>double.tryParse(v??'')==null?'Enter physical quantity':null)), const SizedBox(width:10), Expanded(child:TextFormField(controller:line.reason, decoration: const InputDecoration(labelText:'Reason *'), validator:(v)=>(v??'').trim().length<3?'Minimum 3 characters':null))]), const SizedBox(height:8), TextField(controller:line.notes, decoration: const InputDecoration(labelText:'Line Notes'))]))); }), OutlinedButton.icon(onPressed:()=>setState(()=>_lines.add(_RebalanceLine())), icon:const Icon(Icons.add), label:const Text('Add Lot')), TextField(controller:_notes, maxLines:2, decoration:const InputDecoration(labelText:'Document Notes')), if(_error!=null) Padding(padding:const EdgeInsets.only(top:12),child:Text(_error!,style:TextStyle(color:Theme.of(context).colorScheme.error)))])))), actions:[TextButton(onPressed:_saving?null:()=>Navigator.pop(context),child:const Text('Cancel')), FilledButton(onPressed:_saving?null:_save,child:Text(_saving?'Posting...':'Post Rebalancing'))]);
}
