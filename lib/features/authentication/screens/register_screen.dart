import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../widgets/custom_button.dart';
import '../../../widgets/custom_textfield.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final nameController = TextEditingController();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  final confirmPasswordController = TextEditingController();

  final _formKey = GlobalKey<FormState>();

  @override
  void dispose() {
    nameController.dispose();
    emailController.dispose();
    passwordController.dispose();
    confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                color: AppColors.card,
                elevation: 8,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      children: [
                        Text(
                          "Create Account",
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),

                        const SizedBox(height: 25),

                        CustomTextField(
                          hintText: "Full Name",
                          prefixIcon: Icons.person_outline,
                          controller: nameController,
                        ),

                        const SizedBox(height: 16),

                        CustomTextField(
                          hintText: "Email",
                          prefixIcon: Icons.email_outlined,
                          controller: emailController,
                        ),

                        const SizedBox(height: 16),

                        CustomTextField(
                          hintText: "Password",
                          prefixIcon: Icons.lock_outline,
                          controller: passwordController,
                          obscureText: true,
                        ),

                        const SizedBox(height: 16),

                        CustomTextField(
                          hintText: "Confirm Password",
                          prefixIcon: Icons.lock_reset_outlined,
                          controller: confirmPasswordController,
                          obscureText: true,
                        ),

                        const SizedBox(height: 28),

                        CustomButton(text: "Create Account", onPressed: () {}),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
