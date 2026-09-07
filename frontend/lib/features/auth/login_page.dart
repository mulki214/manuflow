import 'package:flutter/material.dart';

import 'auth_controller.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await widget.auth.login(_email.text, _password.text);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 900;
          return Row(
            children: [
              if (desktop)
                Expanded(
                  child: Container(
                    height: double.infinity,
                    padding: const EdgeInsets.all(64),
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          Color(0xFF0B3B8F),
                          Color(0xFF155EEF),
                          Color(0xFF53B1FD),
                        ],
                      ),
                    ),
                    child: const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _Brand(light: true),
                        Spacer(),
                        Icon(
                          Icons.precision_manufacturing_outlined,
                          color: Colors.white,
                          size: 72,
                        ),
                        SizedBox(height: 28),
                        Text(
                          'Satu sistem untuk seluruh proses manufaktur.',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 38,
                            height: 1.2,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        SizedBox(height: 18),
                        Text(
                          'Kelola penjualan, pembelian, gudang, produksi, kualitas hingga pengiriman dalam satu alur.',
                          style: TextStyle(
                            color: Color(0xFFD1E9FF),
                            fontSize: 17,
                            height: 1.5,
                          ),
                        ),
                        Spacer(),
                        Text(
                          'ERP Manufaktur • Aman dan terintegrasi',
                          style: TextStyle(color: Color(0xFFD1E9FF)),
                        ),
                      ],
                    ),
                  ),
                ),
              Expanded(
                child: Center(
                  child: SingleChildScrollView(
                    padding: EdgeInsets.symmetric(
                      horizontal: desktop ? 72 : 24,
                      vertical: 32,
                    ),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 440),
                      child: Form(
                        key: _formKey,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            if (!desktop) const _Brand(),
                            if (!desktop) const SizedBox(height: 56),
                            Text(
                              'Selamat datang',
                              style: Theme.of(context).textTheme.headlineMedium
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              'Masuk menggunakan akun yang terdaftar untuk melanjutkan.',
                              style: TextStyle(
                                color: Color(0xFF667085),
                                height: 1.5,
                              ),
                            ),
                            const SizedBox(height: 32),
                            TextFormField(
                              controller: _email,
                              keyboardType: TextInputType.emailAddress,
                              autofillHints: const [AutofillHints.email],
                              decoration: const InputDecoration(
                                labelText: 'Email',
                                prefixIcon: Icon(Icons.mail_outline),
                              ),
                              validator: (value) =>
                                  value == null || !value.contains('@')
                                  ? 'Masukkan email yang valid'
                                  : null,
                            ),
                            const SizedBox(height: 18),
                            TextFormField(
                              controller: _password,
                              obscureText: _obscurePassword,
                              autofillHints: const [AutofillHints.password],
                              onFieldSubmitted: (_) => _submit(),
                              decoration: InputDecoration(
                                labelText: 'Password',
                                prefixIcon: const Icon(Icons.lock_outline),
                                suffixIcon: IconButton(
                                  onPressed: () => setState(
                                    () => _obscurePassword = !_obscurePassword,
                                  ),
                                  icon: Icon(
                                    _obscurePassword
                                        ? Icons.visibility_outlined
                                        : Icons.visibility_off_outlined,
                                  ),
                                ),
                              ),
                              validator: (value) =>
                                  value == null || value.length < 8
                                  ? 'Password minimal 8 karakter'
                                  : null,
                            ),
                            if (widget.auth.error != null) ...[
                              const SizedBox(height: 16),
                              Text(
                                widget.auth.error!,
                                style: TextStyle(
                                  color: Theme.of(context).colorScheme.error,
                                ),
                              ),
                            ],
                            const SizedBox(height: 24),
                            SizedBox(
                              height: 52,
                              child: FilledButton(
                                onPressed: widget.auth.isLoading
                                    ? null
                                    : _submit,
                                child: widget.auth.isLoading
                                    ? const SizedBox.square(
                                        dimension: 22,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Text('Masuk'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _Brand extends StatelessWidget {
  const _Brand({this.light = false});
  final bool light;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: light ? Colors.white : const Color(0xFF155EEF),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(
            Icons.factory_outlined,
            color: light ? const Color(0xFF155EEF) : Colors.white,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          'MANUFLOW',
          style: TextStyle(
            fontWeight: FontWeight.w800,
            letterSpacing: 1.5,
            fontSize: 18,
            color: light ? Colors.white : const Color(0xFF101828),
          ),
        ),
      ],
    );
  }
}
