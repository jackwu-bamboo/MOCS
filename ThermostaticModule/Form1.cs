using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using ModbusWrapper;
using System.Reflection;

namespace MultiModuleController
{
    public partial class Form1 : Form
    {
        private static readonly log4net.ILog LOG = log4net.LogManager.GetLogger(MethodBase.GetCurrentMethod().DeclaringType);
        private const float DefaultFrequency = 1; // 默认频率为1Hz
        private const int NumberOfRows = 108;   // 暂时只使用54个阀门
        private const int ValvesPerServer = 108;  // 单个服务器支持108个阀门
        private const int ServerAddress = 0x42;  // 只使用0x42服务器地址
        private const int CheckAddress = 0x701;     // 检查地址
        private const int CheckValue = 0x0F0F;     // 检查
        private const ushort BaseAddress = 0x800; // 起始地址为0x800
        private const int RegistersPerValve = 5;  // 每个阀门占用5个寄存器
        private const float MaxPositivePressure = 1000f;  // 最大正压 (mBar)
        private const float MinNegativePressure = -1000f; // 最大负压 (mBar)
        private const float PsiTomBarCoef = 68.9476f; // PSI转换为mBar的系数 
        private const ushort PressureAddress1 = 0xA00; // 正压写入地址

        private const ushort DutyCycleAddress1 = 0xA20; // 占空比高电平地址
        private const ushort DutyCycleAddress2 = 0xA21; // 占空比低电平地址

        private const float DefaultDutyCycle = 0.5f; // 默认占空比为50%
        private const ushort SystemSwitchAddress = 0xB000; //系统总开关地址
        private const ushort LidTemperatureAddress = 0xB010; //顶盖温度设置地址
        private const ushort TemperatureReadAddress = 0xB020; //温度读取地址

        private Modbus _modbus; // 只使用一个Modbus对象（0x42地址）
        private System.Windows.Forms.Timer pressureTimer; // 添加Timer对象

        public Form1()
        {
            InitializeComponent();
            dataGridViewInit();

            UpdateConnectionStatus("等待连接...", false);

            // 初始化Timer
            pressureTimer = new System.Windows.Forms.Timer();
            pressureTimer.Interval = 2000; // 1秒
            pressureTimer.Tick += PressureTimer_Tick;
            //pressureTimer.Start();

            // 只初始化0x42地址的Modbus对象
            var parameter = new Parameter
            {
                ServerAddr = ServerAddress,
                CheckAddress = CheckAddress,
                CheckValue = CheckValue,
            };

            _modbus = new Modbus(parameter);
           
            Thread connectThread = new Thread(() => ConnectToDevice(_modbus));
            connectThread.Start();

        }

        private void PressureTimer_Tick(object sender, EventArgs e)
        {
            if (_modbus.ConnectState() != 0) return;

            try
            {
                // 禁用正压读取
                //short[] pressureData = new short[1];
                //int result = _modbus.readSensor(PressureAddress1, out pressureData);
                //if (result == 1)
                //{
                //    float pressure = pressureData[0] / 10.0f * PsiTomBarCoef; // 转换为mBar
                //    labelPressure1Value.Text = pressure.ToString("F1");
                //}

                // 读取温度值（从0xB020地址）
                short[] temperatureData = new short[1]; // 读取2个寄存器：顶盖温度和盒体温度
                int tempResult = _modbus.readSensor(TemperatureReadAddress, out temperatureData);
                if (tempResult == 1)
                {
                    // 第一个寄存器是顶盖温度，第二个是盒体温度
                    //float lidTemp = temperatureData[0] / 10.0f; // 转换为实际温度值（保留1位小数）
                    float lidTemp = temperatureData[0] / 10.0f ; // 转换为实际温度值（保留1位小数）
                                                                     //float caseTemp = temperatureData[1] / 10.0f;
                    LOG.Info($"TemperatureRead:" + lidTemp);
                    // 更新界面显示
                    label_Lid_temperature.Text = "温度（实测）：" + lidTemp.ToString("F1"); // 顶盖温度（实测）
                    //label13.Text = caseTemp.ToString("F1"); // 盒体温度（实测）
                }
            }
            catch (Exception ex)
            {
                LOG.Error($"Error reading sensor values: {ex.Message}");
            }
        }

        private void ConnectToDevice(Modbus modbus)
        {
            try
            {
                LOG.Info($"Attempting to connect to Modbus device at address 0x42...");
                Thread.Sleep(3000); // Wait 3 seconds
                Console.WriteLine("Modbus (0x42): " + modbus.ConnectState());
                bool isConnected = (modbus.ConnectState() == 0);
                // Update UI based on connection status
                UpdateConnectionStatus(isConnected ? "连接成功" : "连接失败", isConnected);
                LOG.Info($"Modbus device connection status: " + (isConnected ? "Connected" : "Failed"));
            }
            catch (Exception ex)
            {
                LOG.Error($"Error during Modbus connection attempt: " + ex.Message);
                Console.WriteLine($"Error: {ex.Message}");
                UpdateConnectionStatus("连接失败", false); // Ensure UI reflects failure
            }
        }

        private void UpdateConnectionStatus(string statusText, bool isConnected)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(() => UpdateConnectionStatus(statusText, isConnected)));
                return;
            }

            this.radioButtonConnect.Text = statusText;
            this.radioButtonConnect.Checked = isConnected;
        }

        private void dataGridViewInit()
        {
            // Centralize headers and cell content
            foreach (DataGridViewColumn column in this.dataGridView1.Columns)
            {
                column.HeaderCell.Style.Alignment = DataGridViewContentAlignment.MiddleCenter;
            }
            this.dataGridView1.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;

            // Configure DataGridView
            this.dataGridView1.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            this.dataGridView1.AllowUserToAddRows = false;
            this.dataGridView1.SelectionMode = DataGridViewSelectionMode.FullRowSelect; // Select entire rows
            this.dataGridView1.MultiSelect = true; // Allow multiple row selection

            // Load data rows
            for (int i = 0; i < NumberOfRows; i++)
            {
                this.dataGridView1.Rows.Add(i + 1, DefaultFrequency, DefaultDutyCycle, false);
            }
        }

        private void button_start_Click(object sender, EventArgs e)
        {
            if (_modbus.ConnectState() != 0)
            {
                MessageBox.Show("设备未连接，请确保服务器已连接。", "连接错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // 显示延迟提示并在后台线程执行延迟
            button_start.Enabled = false; // 禁用按钮防止重复点击
            string originalText = button_start.Text;
            
            // 创建后台线程执行延迟倒计时
            Task.Run(() =>
            {
                for (int i = 10; i > 0; i--)
                {
                    // 更新按钮文本显示倒计时
                    this.Invoke(new Action(() =>
                    {
                        button_start.Text = $"启动中...{i}秒";
                    }));
                    Thread.Sleep(1000);
                }

                // 延迟结束后执行启动逻辑
                this.Invoke(new Action(() =>
                {
                    // 设置系统总开关为1，表示启动系统
                    if (SystemSwitch(_modbus, 1))
                    {
                        //pressureTimer start
                        pressureTimer.Start();
                        button_start.Text = "系统已启动";
                        button_start.BackColor = Color.Green;
                    }
                    else
                    {
                        button_start.Text = originalText;
                    }
                    
                    button_start.Enabled = true; // 重新启用按钮
                }));
            });
        }

        //系统使能函数，参数modbus对象，地址，值
        private bool SystemSwitch(Modbus modbus, short value)
        {
            try
            {
                int result = modbus.writeSwitch(SystemSwitchAddress, new short[] { value });
                if (result != 1)
                {
                    MessageBox.Show($"系统使能失败，错误代码：{result}", "通信错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return false;
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"系统使能异常：{ex.Message}", "通信错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return false;
            }
            return true;
        }
        private void button_stop_Click(object sender, EventArgs e)
        {
            if (_modbus.ConnectState() != 0)
            {
                MessageBox.Show("设备未连接，请确保服务器已连接。", "连接错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            //设置所有行的状态为false
            //foreach (DataGridViewRow row in this.dataGridView1.SelectedRows.Cast<DataGridViewRow>().Reverse())
            //{
            //    SetRowStatus(row, false);
            //}
            // 设置系统总开关为0，表示关闭系统
            if (SystemSwitch(_modbus, 0))
            {
                //恢复start button的颜色，，并且显示文字为启动
                button_start.BackColor = Color.White;
                button_start.Text = "启动";

            }
            //停止Timer
            pressureTimer.Stop();
        }

        private void SetRowStatus(DataGridViewRow row, bool status)
        {

            if (row.Cells["freq"].Value == null || row.Cells["status"].Value == null)
            {
                LOG.Warn("Row data is incomplete. Skipping.");
                return;
            }

            int freq = Convert.ToInt32(row.Cells["freq"].Value);
            row.Cells["status"].Value = status;
            int rowIndex = row.Index; // Use row index for address calculation

            // 读取占空比值
            float dutyCycleValue = Convert.ToSingle(row.Cells["DutyRatio"].Value);
            Console.WriteLine($"DutyCycleValue: {dutyCycleValue}");

            try
            {
                // 所有108个阀门都使用同一个Modbus对象（0x42地址）
                Modbus currentModbus = _modbus;
                
                // 发送状态值
                short[] statusData = new short[1];
                statusData[0] = (short)(status ? 1 : 0);
                ushort statusAddr = (ushort)(BaseAddress + rowIndex * RegistersPerValve);
                int statusResult = currentModbus.writeSwitch(statusAddr, statusData);

                //如果输入status为false的话 只需要发送状态值即可
                if (!status)
                {
                    if (statusResult == 1)
                    {
                        LOG.Info($"Successfully set status for valve {rowIndex + 1} to {status}");
                    }
                    else
                    {
                        //设置状态失败
                        MessageBox.Show($"设置状态失败", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        LOG.Error($"Failed to set status for valve {rowIndex + 1}");
                    }
                }
                else
                {
                    // 发送频率值
                    short[] freqData = new short[1];
                    freqData[0] = (short)freq;
                    ushort freqAddr = (ushort)(BaseAddress + rowIndex * RegistersPerValve + 1);
                    int freqResult = currentModbus.writeRegister(freqAddr, freqData);
                    Console.WriteLine($"Frequency: {freq}");

                    // 发送占空比值
                    float period = 1 / (float)freq; // 周期
                    Console.WriteLine($"period: {period}");

                    short highLevel = (short)(period * (1 - dutyCycleValue) * 1000); // 占空比高电平值,毫秒
                    short lowLevel = (short)(period * dutyCycleValue * 1000); // 占空比低电平值，毫秒

                    Console.WriteLine($"High Level: {highLevel}, Low Level: {lowLevel}");
                    //下发高电平值
                    ushort address = (ushort)(BaseAddress + rowIndex * RegistersPerValve + 2);
                    short[] data = new short[] { highLevel };
                    int highTTLResult = currentModbus.writeRegister(address, data);

                    if (highTTLResult != 1)
                    {
                        //设置高电平失败
                        MessageBox.Show($"设置高电平失败", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        LOG.Error($"Failed to set high level");
                    }

                    //下发低电平值
                    address = (ushort)(BaseAddress + rowIndex * RegistersPerValve + 3); ;
                    data[0] = lowLevel;
                    int lowTTLResult = currentModbus.writeRegister(address, data);
                    if (lowTTLResult != 1)
                    {
                        //设置低电平失败
                        MessageBox.Show($"设置低电平失败", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        LOG.Error($"Failed to set low level");
                    }

                    if (freqResult == 1 && statusResult == 1 && highTTLResult == 1 && lowTTLResult == 1)
                    {
                        LOG.Info($"Successfully set data - Valve:{rowIndex + 1}, Freq:{freq}, Status:{status}, DutyCycle:{dutyCycleValue}");
                    }
                    else
                    {
                        LOG.Error($"Failed to send data - Freq result:{freqResult}, Status result:{statusResult}, High TTL result:{highTTLResult}, Low TTL result:{lowTTLResult}");
                        MessageBox.Show($"设置数据失败，错误代码：{freqResult}, {statusResult}, {highTTLResult}, {lowTTLResult}", "通信错误", MessageBoxButtons.OK, MessageBoxIcon.Error);

                    }
                }
            }
            catch (Exception ex)
            {
                LOG.Error($"Error sending Modbus data: {ex.Message}");
                MessageBox.Show($"发送数据异常：{ex.Message}", "通信错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void TextBoxPressure_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode != Keys.Enter) return;

            TextBox textBox = (TextBox)sender;
            if (!float.TryParse(textBox.Text, out float pressureValue))
            {
                MessageBox.Show("请输入有效的气压值", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // 根据正负压类型验证范围
            bool isPositivePressure = textBox == textBoxPressure1;
            if (isPositivePressure)
            {
                if (pressureValue < 0 || pressureValue > MaxPositivePressure)
                {
                    MessageBox.Show($"正压值必须在0~{MaxPositivePressure} mBar之间", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
            }
            else
            {
                if (pressureValue < MinNegativePressure || pressureValue > 0)
                {
                    MessageBox.Show($"负压值必须在{MinNegativePressure}~0 mBar之间", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
            }

            try
            {
                ushort address = PressureAddress1;
                short[] data = new short[] { (short)(pressureValue / PsiTomBarCoef * 10) }; // 转换为整数值，保留1位小数
                int result = _modbus.writeRegister(address, data);

                if (result == 1)
                {
                    MessageBox.Show($"气压{(textBox == textBoxPressure1 ? "1" : "2")}设置成功", "成功", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    LOG.Info($"Successfully set pressure {(textBox == textBoxPressure1 ? "1" : "2")} to {pressureValue}");
                }
                else
                {
                    MessageBox.Show($"设置气压失败，错误代码：{result}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    LOG.Error($"Failed to set pressure - Error code: {result}");
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"设置气压时发生错误：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                LOG.Error($"Error setting pressure: {ex.Message}");
            }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            var result = MessageBox.Show("请先点击停止按钮以确保安全关闭设备。", "关闭提示", MessageBoxButtons.OKCancel, MessageBoxIcon.Information);
            if (result == DialogResult.Cancel)
            {
                e.Cancel = true; // Prevent the form from closing if Cancel is clicked
            }
            else
            {
                base.OnFormClosing(e); // Allow the form to close if OK is clicked
            }
        }

        private void dataGridView1_CellContentClick(object sender, DataGridViewCellEventArgs e)
        {
            // 确保点击的是状态列的复选框
            if (e.ColumnIndex == dataGridView1.Columns["status"].Index && e.RowIndex >= 0)
            {
                if (_modbus.ConnectState() != 0)
                {
                    MessageBox.Show("设备未连接，请确保服务器已连接。", "连接错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                DataGridViewRow row = dataGridView1.Rows[e.RowIndex];
                bool newStatus = !(bool)row.Cells["status"].Value; // 获取切换后的状态
                SetRowStatus(row, newStatus);
            }


        }

        private void textBox_DutyRatio_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode != Keys.Enter) return;

            TextBox textBox = (TextBox)sender;
            if (!float.TryParse(textBox.Text, out float dutyCycleValue))
            {
                MessageBox.Show("请输入有效的占空比值", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // 验证范围
            if (dutyCycleValue < 0 || dutyCycleValue > 1)
            {
                MessageBox.Show("占空比必须在0~1之间", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // 读取lable_ValveIndex的值，作为当前行的索引，并修改行的占空比值
            int rowIndex = int.Parse(label_ValveIndex.Text) - 1; // 减去1以匹配DataGridView的索引
            DataGridViewRow row = dataGridView1.Rows[rowIndex];
            row.Cells["DutyRatio"].Value = dutyCycleValue; // 更新占空比值
            //调用setRowStatus方法
            SetRowStatus(row, (bool)row.Cells["status"].Value); // 重新设置行状态以应用新的占空比值

        }

        private void valve_selected(object sender, DataGridViewCellMouseEventArgs e)
        {
            DataGridViewRow selectedRow = dataGridView1.CurrentRow;
            if (selectedRow == null) return; // 确保选中行不为空
            label_ValveIndex.Text = selectedRow.Cells["index"].Value.ToString();
            textBox_freq.Text = selectedRow.Cells["freq"].Value.ToString();
            textBox_DutyRatio.Text = selectedRow.Cells["DutyRatio"].Value.ToString();
        }

        private void textBox_freq_KeyDown(object sender, KeyEventArgs e)
        {
            //读取textBox_freq的值
            if (e.KeyCode != Keys.Enter) return;
            TextBox textBox = (TextBox)sender;
            if (!int.TryParse(textBox.Text, out int freqValue))
            {
                MessageBox.Show("请输入有效的频率值", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            // 读取lable_ValveIndex的值，作为当前行的索引，并修改行的频率值
            int rowIndex = int.Parse(label_ValveIndex.Text) - 1; // 减去1以匹配DataGridView的索引
            DataGridViewRow row = dataGridView1.Rows[rowIndex];
            row.Cells["freq"].Value = freqValue; // 更新占空比值
            //调用setRowStatus方法
            SetRowStatus(row, (bool)row.Cells["status"].Value); // 重新设置行状态以应用新的占空比值
        }

        private void label5_Click(object sender, EventArgs e)
        {

        }

        private void groupBox1_Enter(object sender, EventArgs e)
        {

        }

        private void label8_Click(object sender, EventArgs e)
        {

        }

        private void textBox_Lid_temperature_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode != Keys.Enter) return;

            TextBox textBox = (TextBox)sender;
            if (!float.TryParse(textBox.Text, out float temperatureValue))
            {
                MessageBox.Show("请输入有效的温度值", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            temperatureValue = temperatureValue ;
            //temperatureValue = temperatureValue ;

            // 验证温度范围（例如：0-100℃）
            if (temperatureValue < 0 || temperatureValue > 100)
            {
                MessageBox.Show("温度值必须在0~100℃之间", "输入错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // 检查设备连接状态
            if (_modbus.ConnectState() != 0)
            {
                MessageBox.Show("设备未连接，请确保服务器已连接。", "连接错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            try
            {
                // 将温度值转换为short类型（根据实际协议可能需要乘以10保留1位小数）
                short[] data = new short[] { (short)(temperatureValue * 10) };
                int result = _modbus.writeRegister(LidTemperatureAddress, data);

                if (result == 1)
                {
                    MessageBox.Show($"温度设置成功：{temperatureValue  }℃", "成功", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    LOG.Info($"Successfully set lid temperature to {temperatureValue+10}℃");
                }
                else
                {
                    MessageBox.Show($"设置温度失败，错误代码：{result}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    LOG.Error($"Failed to set lid temperature - Error code: {result}");
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"设置温度时发生错误：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                LOG.Error($"Error setting lid temperature: {ex.Message}");
            }
        }
    }
}
