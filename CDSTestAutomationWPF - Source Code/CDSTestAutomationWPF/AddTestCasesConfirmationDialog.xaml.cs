using System;
using System.Windows;

namespace CDSTestAutomationWPF
{
    /// <summary>
    /// Confirmation dialog for adding test cases to TFS test suite
    /// </summary>
    public partial class AddTestCasesConfirmationDialog : Window
    {
        public AddTestCasesConfirmationDialog()
        {
            InitializeComponent();
        }

        public void SetConfirmationData(SuiteConfirmationData data, int testCaseCount)
        {
            if (data == null)
                return;

            // Create formatted message
            string message = $@"You are about to add {testCaseCount} test case(s) to the following suite:

═══════════════════════════════════════════════════════════

TEST PLAN:
  • Name: {data.TestPlanName}
  • ID: {data.TestPlanId}

TEST SUITE:
  • Name: {data.SuiteName}
  • ID: {data.SuiteId}
  • Type: {(data.IsStaticSuite ? "Static" : "Dynamic/Query-based")}

PROJECT DETAILS:
  • Area Path: {data.AreaPath}
  • Iteration Path: {data.IterationPath}

═══════════════════════════════════════════════════════════

Do you want to proceed?";

            MessageTextBlock.Text = message;
        }

        private void YesButton_Click(object sender, RoutedEventArgs e)
        {
            this.DialogResult = true;
            this.Close();
        }

        private void NoButton_Click(object sender, RoutedEventArgs e)
        {
            this.DialogResult = false;
            this.Close();
        }
    }
}
