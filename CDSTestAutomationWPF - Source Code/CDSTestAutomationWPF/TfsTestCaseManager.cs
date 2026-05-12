using System;
using System.Collections.Generic;
using System.Windows;
using Microsoft.TeamFoundation.TestManagement.Client;

namespace CDSTestAutomationWPF
{
    /// <summary>
    /// Manages TFS test case operations including adding test cases to test suites
    /// </summary>
    public class TfsTestCaseManager
    {
        private readonly ITestManagementTeamProject _project;
        private readonly ITestPlan _testPlan;
        private readonly IStaticTestSuite _targetSuite;

        public TfsTestCaseManager(ITestManagementTeamProject project, ITestPlan testPlan, IStaticTestSuite targetSuite)
        {
            _project = project;
            _testPlan = testPlan;
            _targetSuite = targetSuite;
        }

        /// <summary>
        /// Gets comprehensive information about the target suite for confirmation display
        /// </summary>
        public SuiteConfirmationData GetSuiteConfirmationData()
        {
            try
            {
                var suiteData = new SuiteConfirmationData
                {
                    SuiteId = _targetSuite.Id,
                    SuiteName = _targetSuite.Title,
                    TestPlanId = _testPlan.Id,
                    TestPlanName = _testPlan.Name,
                    AreaPath = _project.WitProject.Name,
                    IterationPath = _testPlan.Iteration.Path,
                    IsStaticSuite = _targetSuite.TestSuiteType == TestSuiteType.StaticTestSuite
                };

                return suiteData;
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error retrieving suite information: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                return null;
            }
        }

        /// <summary>
        /// Adds test cases to the target static test suite
        /// </summary>
        public bool AddTestCasesToSuite(List<ITestPoint> testPoints)
        {
            try
            {
                // Validate suite type
                if (_targetSuite.TestSuiteType != TestSuiteType.StaticTestSuite)
                {
                    MessageBox.Show(
                        "Cannot add test cases to this suite type. Only static test suites support adding test cases.",
                        "Invalid Suite Type",
                        MessageBoxButton.OK,
                        MessageBoxImage.Warning);
                    return false;
                }

                // Add each test case to the suite
                foreach (ITestPoint testPoint in testPoints)
                {
                    // Check if test case already exists in suite
                    bool alreadyExists = false;
                    foreach (ITestCase existingCase in _targetSuite.TestCases)
                    {
                        if (existingCase.Id == testPoint.TestCaseId)
                        {
                            alreadyExists = true;
                            break;
                        }
                    }

                    if (!alreadyExists)
                    {
                        var testCase = testPoint.TestCase;
                        _targetSuite.Entries.Add(testCase);
                    }
                }

                // Save changes
                _targetSuite.Save();
                return true;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"Error adding test cases to suite: {ex.Message}",
                    "Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);
                return false;
            }
        }

        /// <summary>
        /// Validates that the target suite is a valid static test suite
        /// </summary>
        public bool ValidateSuite()
        {
            if (_targetSuite == null)
            {
                MessageBox.Show("No suite selected", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                return false;
            }

            if (_targetSuite.TestSuiteType != TestSuiteType.StaticTestSuite)
            {
                MessageBox.Show(
                    "Only static test suites support adding test cases. Dynamic (query-based) suites cannot have test cases added directly.",
                    "Invalid Suite Type",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return false;
            }

            return true;
        }
    }

    /// <summary>
    /// Data class for suite confirmation information
    /// </summary>
    public class SuiteConfirmationData
    {
        public int SuiteId { get; set; }
        public string SuiteName { get; set; }
        public int TestPlanId { get; set; }
        public string TestPlanName { get; set; }
        public string AreaPath { get; set; }
        public string IterationPath { get; set; }
        public bool IsStaticSuite { get; set; }
    }
}
