using System;
using System.Collections.Generic;
using System.Collections;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using System.Threading;
using System.Diagnostics;

using Microsoft.TeamFoundation.Client;
using Microsoft.TeamFoundation.TestManagement.Client;
using System.Data;
using System.ComponentModel;

namespace CDSTestAutomationWPF
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();

            //[OK]: moving tfsProjects to config
            cmbBxProject.ItemsSource = Properties.Settings.Default.tfsProjectFilter;

            System.Collections.Specialized.StringCollection heavySuites = Properties.Settings.Default.heavySuiteNames;

            foreach (string heavySuite in heavySuites)
                loadHeavySuites.Content += heavySuite + (heavySuites.IndexOf(heavySuite) != heavySuites.Count - 1 ? ", " : "");

            cmbBoxEnvironment.Items.Add("CDSDEV");
            cmbBoxEnvironment.Items.Add("CDSQA");
            cmbBoxEnvironment.Items.Add("DISDEV");
            cmbBoxEnvironment.Items.Add("AMSQA");
            cmbBoxEnvironment.Items.Add("CDSSDR");
            cmbBoxEnvironment.Items.Add("LTIDQA");
            cmbBoxEnvironment.Items.Add("TDMQA");

            //[OK]: selecting QA by default
            cmbBoxEnvironment.SelectedIndex = 1;

            //getting creds from config
            tbUserName.Text = Properties.Settings.Default.oraUserName;
            tbPassword.Password = Properties.Settings.Default.oraPassword;
                        
            //LoadTestPlanView("CDSCCAL");
            buttonExecute.IsEnabled = false;
            rerunFailedTestCasesBtn.IsEnabled = false;

            this.lastRunId = -1;

                                    // Setup drag and drop
                                    ListViewTestCase.PreviewMouseLeftButtonDown += ListViewTestCase_PreviewMouseLeftButtonDown;
                                    ListViewSelected.PreviewMouseLeftButtonDown += ListViewSelected_PreviewMouseLeftButtonDown;
                                    TestPlanView.AllowDrop = true;
                                    TestPlanView.DragOver += TreeView_DragOver;
                                    TestPlanView.Drop += TreeView_Drop;
        }

        //[OK]: moving collection URL to config
        static TfsTeamProjectCollection tfs = TfsTeamProjectCollectionFactory.GetTeamProjectCollection(new Uri(Properties.Settings.Default.tfsCollection));

        int lastRunId;

        ITestManagementTeamProject project;

        public void LoadTestPlanView(String projectName)
        {
            System.GC.Collect();

            if (projectName != null)
            {
                try
                {
                    project = tfs.GetService<ITestManagementService>().GetTeamProject(projectName);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message);
                }

                Console.WriteLine("project fetched");

                ListViewTestCase.ItemsSource = null;
                TestPlanView.Items.Clear();
                                
                
                //[OK]: adding filter for test plans
                string strQuery = "Select * From TestPlan "
                    + Properties.Settings.Default.tfsTestPlanFilter;

                if(cbShowInactive.IsChecked == false)
                {
                    int iWherePosition = strQuery.ToUpper().IndexOf("WHERE");
                    if (iWherePosition != -1)
                    {
                        strQuery = strQuery.Insert(iWherePosition + 6, "(");
                        strQuery = strQuery.Insert(strQuery.Length, ")");
                        strQuery = strQuery + " AND PlanState <> 'Inactive'";

                    }
                    else
                    {
                        strQuery = strQuery + "WHERE PlanState <> 'Inactive'";
                    }
                }

                try
                {
                    ITestPlanCollection plans = project.TestPlans.Query(strQuery);

                    TreeViewItem root = null;
                    root = new TreeViewItem();
                    root.Header = ImageHelpers.CreateHeader(project.WitProject.Name, ItemTypes.TeamProject);
                    TestPlanView.Items.Add(root);

                    foreach (ITestPlan plan in plans)
                    {
                        TreeViewItem plan_tree = new TreeViewItem();
                        plan_tree.Header = ImageHelpers.CreateHeader(plan.Name, ItemTypes.TestPlan);

                        if (plan.RootSuite != null && plan.RootSuite.Entries.Count > 0)
                            GetPlanSuites(plan.RootSuite.Entries, plan_tree);

                        root.Items.Add(plan_tree);

                        //[OK]: collapsed by default
                        plan_tree.IsExpanded = false;
                    }

                    root.IsExpanded = true;
                }
                catch(Exception ex)
                {
                    MessageBox.Show(ex.Message);
                }
            }
        }

        void GetPlanSuites(ITestSuiteEntryCollection suites, TreeViewItem tree_item)
        {
            foreach (ITestSuiteEntry suite_entry in suites.OrderBy(suite => suite.Title))
            {
                //ORIG
                //IStaticTestSuite suite = suite_entry.TestSuite as IStaticTestSuite;

                //NEW
                ITestSuiteBase suite = suite_entry.TestSuite as ITestSuiteBase;

                if (suite != null 
                    && (
                        (loadHeavySuites.IsChecked == false && !Properties.Settings.Default.heavySuiteNames.Contains(suite.Title))
                        || (loadHeavySuites.IsChecked == true)
                       ))
                {
                    TreeViewItem suite_tree = new TreeViewItem();
                    suite_tree.Header = ImageHelpers.CreateHeader(suite.Title, ItemTypes.TestSuite);

                    suite_tree.Tag = suite.Id;

                    tree_item.Items.Add(suite_tree);

                    //ORIG
                    //if (suite.Entries.Count > 0)
                    //    GetPlanSuites(suite.Entries, suite_tree);

                    //NEW
                    if (suite_entry.EntryType == TestSuiteEntryType.StaticTestSuite)
                    {
                        if (((IStaticTestSuite)suite).Entries.Count > 0)
                            GetPlanSuites(((IStaticTestSuite)suite).Entries, suite_tree);
                    }
                    
                }
            }
        }

        private void SelectionChanged(object sender, RoutedPropertyChangedEventArgs<Object> e)
        {
            //Clear previous items
            ListViewTestCase.ItemsSource = null;

            Console.WriteLine("Tree item clicked|" + ((TreeViewItem)e.NewValue) + "|" + ((TreeViewItem)e.NewValue).Tag);
            
            if ((TreeViewItem)e.NewValue != null)
            {
                if (((TreeViewItem)e.NewValue).Tag != null)
                {
                    //Return selectd Suite ID 
                    int suiteId = Convert.ToInt32(((TreeViewItem)e.NewValue).Tag.ToString());

                    ITestSuiteBase suite = project.TestSuites.Find(suiteId);

                    ITestPlan plan = suite.Plan;

                    ITestPointCollection testPoints =
                        plan.QueryTestPoints(string.Format("SELECT * FROM TestPoint WHERE RecursiveSuiteId = {0}", suiteId));

                    Console.WriteLine("SuiteID: " + suiteId);

                    List <TestCasePoint> items = new List<TestCasePoint>();                    
                    
                    foreach (ITestPoint tp in testPoints)
                    {
                        items.Add(new TestCasePoint() { testPoint = tp });                                               
                    }
                                    
                    ListViewTestCase.ItemsSource = items;

                    Console.WriteLine("TEST: " + e.OriginalSource.ToString());
                    
                }
            }            
        }

        private void RightClickSuite(object sender, EventArgs e)
        {

        }


        private void btnRight_Click(object sender, RoutedEventArgs e)
        {
            IList selectedItems = ListViewTestCase.SelectedItems;

            if (ListViewTestCase.SelectedItem != null)
            {
                foreach (var lvi in selectedItems)
                {
                    if (!ListViewSelected.Items.Contains(lvi))
                        ListViewSelected.Items.Add(lvi);
                }
            }

            ListViewTestCase.UnselectAll();

            enableExecute();

            Console.WriteLine("Count: " + ListViewSelected.Items.Count);
        }

        private void btnLeft_Click(object sender, RoutedEventArgs e)
        {
            var selected = ListViewSelected.SelectedItems.Cast<Object>().ToArray();
            
            foreach (var item in selected) 
                ListViewSelected.Items.Remove(item);

            enableExecute();
        }

        private void btnAllRight_Click(object sender, RoutedEventArgs e)
        {
            ListViewTestCase.SelectAll();
            btnRight_Click(sender, e);
        }

        private void btnAllLeft_Click(object sender, RoutedEventArgs e)
        {
            ListViewSelected.Items.Clear();

            enableExecute();
        }

        private void cmbBxProject_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            LoadTestPlanView(cmbBxProject.SelectedItem.ToString().Trim());
        }

        private void buttonExecute_Click(object sender, RoutedEventArgs e)
        {
            someMethod();
            /*buttonExecute.IsEnabled = false;

            List<ITestPoint> tpList = new List<ITestPoint>();
            foreach (TestCasePoint tp in ListViewSelected.Items)
            {
                tpList.Add(tp.testPoint);
                break;
            }

            ITestPlan plan = tpList[0].Plan;

            ITestPointCollection testPoints =
                    plan.QueryTestPoints(string.Format("SELECT * FROM TestPoint WHERE TestCaseId = {0}", -1));

            testPoints.Clear();

            foreach (TestCasePoint tp in ListViewSelected.Items)
            {
                testPoints.Add(tp.testPoint);
            }

            TestRun testRun = new TestRun(project, plan);

            new Thread(() =>
            {
                Thread.CurrentThread.IsBackground = true;
                
                //testRun.executeRun(testPoints);
            }).Start();*/

            //ListViewSelected.Items.Clear();
        }

        private async void someMethod()
        {
            if(ListViewSelected.Items.Count == 0)
                return;

            //buttonExecute.IsEnabled = false;

            string runName = txtBxRunName.Text;
            string environment = "default";

            switch (cmbBoxEnvironment.SelectedItem.ToString())
            {
                case "CDSQA":
                    environment = Properties.Settings.Default.qaServer;
                    break;

                case "CDSDEV":
                    environment = Properties.Settings.Default.devServer;
                    break;

                case "DISDEV":
                    environment = Properties.Settings.Default.disdevServer;
                    break;

                case "AMSQA":
                    environment = Properties.Settings.Default.amsqaServer;
                    break;

                case "CDSSDR":
                    environment = Properties.Settings.Default.cdsdrServer;
                    break;

                case "LTIDQA":
                    environment = Properties.Settings.Default.ltidqaServer;
                    break;

                case "TDMQA":
                    environment = Properties.Settings.Default.tdmqaServer;
                    break;
            }

            string userName = tbUserName.Text;
            string password = tbPassword.Password;
                       
            ITestPointCollection testPoints =
                ((TestCasePoint)ListViewSelected.Items[0]).testPoint.Plan.QueryTestPoints(string.Format("SELECT * FROM TestPoint WHERE TestCaseId = {0}", -1));

            //Console.WriteLine("TYPE: " + testPoints.);

            foreach (TestCasePoint tp in ListViewSelected.Items)
            {
                testPoints.Add(tp.testPoint);
            }

            executionStartTime.Text = System.DateTime.Now.ToString();
            executionFinishTime.Text = "";

            var progress = new Progress<int>(s => refreshResults(s));
            await Task.Factory.StartNew(() => TestRun.LongWork(progress, project, testPoints, runName, environment, userName, password),
                                TaskCreationOptions.LongRunning);

            executionFinishTime.Text = System.DateTime.Now.ToString();

            rerunFailedTestCasesBtn.IsEnabled = true;
        }

        private void rerunFailedTestCases(object sender, RoutedEventArgs e)
        {
            if (lastRunId == -1)
                return;            

            
            foreach (ITestCaseResult result in project.TestRuns.Find(lastRunId).QueryResultsByOutcome(TestOutcome.Passed))
            {
                foreach (TestCasePoint listViewItem in ListViewSelected.Items)
                    if (Convert.ToString(System.Web.UI.DataBinder.Eval(listViewItem, "ID")) == Convert.ToString(result.TestCaseId))
                    {
                        Console.WriteLine("Result TC ID: " + Convert.ToString(result.TestCaseId));
                        Console.WriteLine("Convert Id: " + Convert.ToString(System.Web.UI.DataBinder.Eval(listViewItem, "ID")));
                        Console.WriteLine("Failed ID = " + Convert.ToString(System.Web.UI.DataBinder.Eval(listViewItem, "ID")));
                        Console.WriteLine("Position = " + ListViewSelected.Items.IndexOf(listViewItem));

                        ListViewSelected.Items.RemoveAt(ListViewSelected.Items.IndexOf(listViewItem));                        
                        break;
                    }
            }

            someMethod();

        }

        private void enableExecute()
        {
            if (ListViewSelected.Items.Count > 0)
                buttonExecute.IsEnabled = true;
            else
                buttonExecute.IsEnabled = false;
        }

        private void btnRefresh_Click(object sender, RoutedEventArgs e)
        {
            refreshResults(122383);            
        }

        private void refreshResults(int runID)
        {
            this.lastRunId = runID;

            TreeViewResults.Items.Clear();

            ITestRun testRun = project.TestRuns.Find(runID);

            foreach (TestOutcome outcome in (TestOutcome[])Enum.GetValues(typeof(TestOutcome)))
            {
                //For some reason all cases are showing up as Unspecified so removing them
                //if (outcome == TestOutcome.Unspecified)
                //    continue; 

                ITestCaseResultCollection results = testRun.QueryResultsByOutcome(outcome);

                if (results.Count > 0)
                {
                    TreeViewItem root = new TreeViewItem();
                    
                    root.Header = choseImageHelper(outcome, outcome.ToString() + ": " + results.Count);
                    TreeViewResults.Items.Add(root);

                    foreach (ITestCaseResult result in results)
                    {
                        root.Items.Add(string.Format("{0}\t{1}", result.TestCaseId, result.TestCaseTitle));
                        TextBlock tempTextBlock = new TextBlock();
                        Hyperlink tempHL = new Hyperlink(new Run(result.TestRunId.ToString()))
                        {
                            NavigateUri = new Uri(Properties.Settings.Default.tfsCollection + "/" + cmbBxProject.SelectedValue + Properties.Settings.Default.testRunLink + result.TestRunId.ToString())
                        };
                        tempHL.RequestNavigate += new RequestNavigateEventHandler(Hyperlink_RequestNavigate);
                        tempTextBlock.Inlines.Add("This is a link to Run ID: ");
                        tempTextBlock.Inlines.Add(tempHL);
                        root.Items.Add(tempTextBlock);
                    }

                    root.IsExpanded = true;
                }
            }
        }

        private StackPanel choseImageHelper(TestOutcome outcome, String title)
        {
            StackPanel panel;
            if (outcome == TestOutcome.Passed)
                panel = ImageHelpers.CreateHeader(title, ItemTypes.Passed);
            else if (outcome == TestOutcome.Failed)
                panel = ImageHelpers.CreateHeader(title, ItemTypes.Failed);
            else
                panel = ImageHelpers.CreateHeader(title, ItemTypes.Alert);
            
            return panel;
        }

        private StackPanel GetImageForTree (TestOutcome outcome, PostProcessState postProcessState, String title)
        {
            StackPanel panel;
            ItemTypes itemType;

            //TODO: call method to try to pass postProcessState = complete
            /*switch(outcome)
                case TestOutcome.Passed*/

            if (outcome == TestOutcome.Passed)
                panel = ImageHelpers.CreateHeader(title, ItemTypes.Passed);
            else if (outcome == TestOutcome.Failed)
                panel = ImageHelpers.CreateHeader(title, ItemTypes.Failed);
            else
                panel = ImageHelpers.CreateHeader(title, ItemTypes.Alert);

            return panel;
        }
        

        private void ButtonTestConnection_Click(object sender, RoutedEventArgs e)
        {
            string oraServer = "default";

            switch (cmbBoxEnvironment.SelectedItem.ToString())
            {
                case "CDSQA":
                    oraServer = Properties.Settings.Default.qaServer;
                    break;

                case "CDSDEV":
                    oraServer = Properties.Settings.Default.devServer;
                    break;

                case "DISDEV":
                    oraServer = Properties.Settings.Default.disdevServer;
                    break;

                case "AMSQA":
                    oraServer = Properties.Settings.Default.amsqaServer;
                    break;

                case "CDSSDR":
                    oraServer = Properties.Settings.Default.cdsdrServer;
                    break;

                case "LTIDQA":
                    oraServer = Properties.Settings.Default.ltidqaServer;
                    break;
                case "TDMQA":
                    oraServer = Properties.Settings.Default.tdmqaServer;
                    break;
            }


                    oraClass oracleConnection = new oraClass (oraServer, tbUserName.Text, tbPassword.Password);

            MessageBoxResult result;
            
            try
            {
                DataTable resultTable = oracleConnection.runQuery("select ora_database_name from dual");

                if (resultTable.Rows.Count != 0)
                    result = MessageBox.Show(string.Format("Connected to {0}:\n\n{1}", resultTable.Rows[0][0].ToString(), oraServer));
            }
            catch (Exception ex)
            {
                MessageBox.Show(string.Format("Error connecting to {0}: {1}", oraServer, ex.Message));
            }

            //else 
            //    result = MessageBox.Show("No Result from CDS!");
        }


        private void cbShowInactive_Checked(object sender, RoutedEventArgs e)
        {
            if (cmbBxProject.SelectedItem.ToString().Trim() != null)
                MessageBox.Show (
                    "Event Handler is not implemented yet. To get Inactive test plans, please, reconnect to the project",
                    "Functionality not implemented",
                     MessageBoxButton.OK,
                     MessageBoxImage.Warning);
        }

        private void ListViewTestCase_MouseDoubleClick(object sender, MouseButtonEventArgs e)
        {
            btnRight_Click(sender, e);
        }

        private void ListViewSelected_MouseDoubleClick(object sender, MouseButtonEventArgs e)
        {
            btnLeft_Click(sender, e);
        }

        private void LoadTestPlanView(object sender, RoutedEventArgs e)
        {
            this.LoadTestPlanView(cmbBxProject.SelectedItem.ToString().Trim());
        }

        private void Hyperlink_RequestNavigate(object sender, RequestNavigateEventArgs e)
        {
            Process.Start(new ProcessStartInfo(e.Uri.AbsoluteUri));
            e.Handled = true;
        }

        private void ListViewTestCase_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (ListViewTestCase.SelectedItems.Count > 0)
            {
                DragDrop.DoDragDrop(ListViewTestCase, ListViewTestCase.SelectedItems, DragDropEffects.Copy);
            }
        }

        private void ListViewSelected_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (ListViewSelected.SelectedItems.Count > 0)
            {
                DragDrop.DoDragDrop(ListViewSelected, ListViewSelected.SelectedItems, DragDropEffects.Copy);
            }
        }

        private void TreeView_DragOver(object sender, DragEventArgs e)
        {
            e.Effects = DragDropEffects.Copy;
            e.Handled = true;
        }

        private bool TryAddTestsToSelectedSuite(IList sourceItems, string successMessage)
        {
            if (sourceItems == null || sourceItems.Count == 0)
            {
                MessageBox.Show("Please select test cases to add to a suite.", "No Test Cases Selected", MessageBoxButton.OK, MessageBoxImage.Warning);
                return false;
            }

            TreeViewItem selectedTreeItem = (TreeViewItem)TestPlanView.SelectedItem;
            if (selectedTreeItem == null || selectedTreeItem.Tag == null)
            {
                MessageBox.Show("Please select a test suite first.", "No Suite Selected", MessageBoxButton.OK, MessageBoxImage.Warning);
                return false;
            }

            int suiteId = Convert.ToInt32(selectedTreeItem.Tag.ToString());
            ITestSuiteBase suite = project.TestSuites.Find(suiteId);

            if (suite.TestSuiteType != TestSuiteType.StaticTestSuite)
            {
                MessageBox.Show(
                    "You can only add test cases to static test suites. The selected suite is dynamic/query-based.",
                    "Invalid Suite Type",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return false;
            }

            IStaticTestSuite staticSuite = (IStaticTestSuite)suite;
            ITestPlan plan = suite.Plan;
            TfsTestCaseManager manager = new TfsTestCaseManager(project, plan, staticSuite);

            if (!manager.ValidateSuite())
                return false;

            SuiteConfirmationData confirmData = manager.GetSuiteConfirmationData();
            if (confirmData == null)
                return false;

            AddTestCasesConfirmationDialog dialog = new AddTestCasesConfirmationDialog();
            dialog.Owner = this;
            dialog.SetConfirmationData(confirmData, sourceItems.Count);

            if (dialog.ShowDialog() != true)
                return false;

            List<ITestPoint> testPointsToAdd = new List<ITestPoint>();
            foreach (TestCasePoint tcp in sourceItems)
            {
                testPointsToAdd.Add(tcp.testPoint);
            }

            if (manager.AddTestCasesToSuite(testPointsToAdd))
            {
                MessageBox.Show(
                    string.Format(successMessage, sourceItems.Count, staticSuite.Title),
                    "Success",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);

                LoadTestPlanView(cmbBxProject.SelectedItem.ToString().Trim());
                return true;
            }

            return false;
        }

        private void TreeView_Drop(object sender, DragEventArgs e)
        {
            try
            {
                if (!e.Data.GetDataPresent("System.Collections.IList"))
                    return;

                IList droppedItems = (IList)e.Data.GetData("System.Collections.IList");
                if (TryAddTestsToSelectedSuite(droppedItems, "Successfully added {0} test case(s) to suite '{1}' via drag and drop."))
                    e.Effects = DragDropEffects.Copy;
                else
                    e.Effects = DragDropEffects.None;
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error during drag and drop: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                e.Effects = DragDropEffects.None;
            }

            e.Handled = true;
        }

        private void btnAddToSuite_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                TryAddTestsToSelectedSuite(ListViewSelected.Items, "Successfully added {0} test case(s) to suite '{1}'.");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error adding test cases to suite: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void btnAddTestCasesToRunSuite_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                TryAddTestsToSelectedSuite(ListViewSelected.Items, "Successfully added {0} test case(s) to suite '{1}'.");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error adding test cases to suite: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ListViewTestCase_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {

        }
    }
}
