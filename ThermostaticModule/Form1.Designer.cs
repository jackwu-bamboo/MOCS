namespace MultiModuleController
{
    partial class Form1
    {
        /// <summary>
        /// 必需的设计器变量。
        /// </summary>
        // private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// 清理所有正在使用的资源。
        /// </summary>

        #region Windows 窗体设计器生成的代码

        /// <summary>
        /// 设计器支持所需的方法 - 不要修改
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            this.radioButtonConnect = new System.Windows.Forms.RadioButton();
            this.dataGridView1 = new System.Windows.Forms.DataGridView();
            this.index = new System.Windows.Forms.DataGridViewTextBoxColumn();
            this.freq = new System.Windows.Forms.DataGridViewTextBoxColumn();
            this.DutyRatio = new System.Windows.Forms.DataGridViewTextBoxColumn();
            this.status = new System.Windows.Forms.DataGridViewCheckBoxColumn();
            this.button_start = new System.Windows.Forms.Button();
            this.button_stop = new System.Windows.Forms.Button();
            this.labelPressure1 = new System.Windows.Forms.Label();
            this.textBoxPressure1 = new System.Windows.Forms.TextBox();
            this.labelPressure1Value = new System.Windows.Forms.Label();
            this.label1 = new System.Windows.Forms.Label();
            this.label2 = new System.Windows.Forms.Label();
            this.textBox_DutyRatio = new System.Windows.Forms.TextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.textBox_freq = new System.Windows.Forms.TextBox();
            this.label4 = new System.Windows.Forms.Label();
            this.label_ValveIndex = new System.Windows.Forms.Label();
            this.label5 = new System.Windows.Forms.Label();
            this.textBox1 = new System.Windows.Forms.TextBox();
            this.groupBox1 = new System.Windows.Forms.GroupBox();
            this.groupBox2 = new System.Windows.Forms.GroupBox();
            this.label12 = new System.Windows.Forms.Label();
            this.label11 = new System.Windows.Forms.Label();
            this.label10 = new System.Windows.Forms.Label();
            this.label9 = new System.Windows.Forms.Label();
            this.textBox2 = new System.Windows.Forms.TextBox();
            this.label6 = new System.Windows.Forms.Label();
            this.groupBox3 = new System.Windows.Forms.GroupBox();
            this.textBox_Lid_temperature = new System.Windows.Forms.TextBox();
            this.label13 = new System.Windows.Forms.Label();
            this.label14 = new System.Windows.Forms.Label();
            this.label8 = new System.Windows.Forms.Label();
            this.label_Lid_temperature = new System.Windows.Forms.Label();
            ((System.ComponentModel.ISupportInitialize)(this.dataGridView1)).BeginInit();
            this.groupBox1.SuspendLayout();
            this.groupBox2.SuspendLayout();
            this.groupBox3.SuspendLayout();
            this.SuspendLayout();
            // 
            // radioButtonConnect
            // 
            this.radioButtonConnect.AutoSize = true;
            this.radioButtonConnect.Cursor = System.Windows.Forms.Cursors.Arrow;
            this.radioButtonConnect.Location = new System.Drawing.Point(1375, 13);
            this.radioButtonConnect.Margin = new System.Windows.Forms.Padding(4);
            this.radioButtonConnect.Name = "radioButtonConnect";
            this.radioButtonConnect.Size = new System.Drawing.Size(118, 19);
            this.radioButtonConnect.TabIndex = 0;
            this.radioButtonConnect.Text = "设备连接状态";
            this.radioButtonConnect.UseVisualStyleBackColor = true;
            // 
            // dataGridView1
            // 
            this.dataGridView1.AllowUserToResizeRows = false;
            this.dataGridView1.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            this.dataGridView1.Columns.AddRange(new System.Windows.Forms.DataGridViewColumn[] {
            this.index,
            this.freq,
            this.DutyRatio,
            this.status});
            this.dataGridView1.Location = new System.Drawing.Point(17, 25);
            this.dataGridView1.Margin = new System.Windows.Forms.Padding(4);
            this.dataGridView1.Name = "dataGridView1";
            this.dataGridView1.RowHeadersWidth = 51;
            this.dataGridView1.RowTemplate.Height = 23;
            this.dataGridView1.Size = new System.Drawing.Size(581, 549);
            this.dataGridView1.TabIndex = 1;
            this.dataGridView1.CellContentClick += new System.Windows.Forms.DataGridViewCellEventHandler(this.dataGridView1_CellContentClick);
            this.dataGridView1.RowHeaderMouseClick += new System.Windows.Forms.DataGridViewCellMouseEventHandler(this.valve_selected);
            // 
            // index
            // 
            this.index.HeaderText = "电磁阀编号";
            this.index.MinimumWidth = 6;
            this.index.Name = "index";
            this.index.Width = 125;
            // 
            // freq
            // 
            this.freq.HeaderText = "开关频率";
            this.freq.MinimumWidth = 6;
            this.freq.Name = "freq";
            this.freq.Width = 125;
            // 
            // DutyRatio
            // 
            this.DutyRatio.HeaderText = "占空比";
            this.DutyRatio.MinimumWidth = 6;
            this.DutyRatio.Name = "DutyRatio";
            this.DutyRatio.Width = 125;
            // 
            // status
            // 
            this.status.HeaderText = "开关";
            this.status.MinimumWidth = 6;
            this.status.Name = "status";
            this.status.Resizable = System.Windows.Forms.DataGridViewTriState.True;
            this.status.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Automatic;
            this.status.Width = 125;
            // 
            // button_start
            // 
            this.button_start.Font = new System.Drawing.Font("宋体", 20F);
            this.button_start.Location = new System.Drawing.Point(1029, 413);
            this.button_start.Margin = new System.Windows.Forms.Padding(4);
            this.button_start.Name = "button_start";
            this.button_start.Size = new System.Drawing.Size(200, 62);
            this.button_start.TabIndex = 2;
            this.button_start.Text = "启动";
            this.button_start.UseVisualStyleBackColor = true;
            this.button_start.Click += new System.EventHandler(this.button_start_Click);
            // 
            // button_stop
            // 
            this.button_stop.Font = new System.Drawing.Font("宋体", 20F);
            this.button_stop.Location = new System.Drawing.Point(1293, 413);
            this.button_stop.Margin = new System.Windows.Forms.Padding(4);
            this.button_stop.Name = "button_stop";
            this.button_stop.Size = new System.Drawing.Size(200, 62);
            this.button_stop.TabIndex = 3;
            this.button_stop.Text = "停止";
            this.button_stop.UseVisualStyleBackColor = true;
            this.button_stop.Click += new System.EventHandler(this.button_stop_Click);
            // 
            // labelPressure1
            // 
            this.labelPressure1.AutoSize = true;
            this.labelPressure1.Location = new System.Drawing.Point(619, 45);
            this.labelPressure1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.labelPressure1.Name = "labelPressure1";
            this.labelPressure1.Size = new System.Drawing.Size(130, 15);
            this.labelPressure1.TabIndex = 4;
            this.labelPressure1.Text = "设置正压（mBar):";
            // 
            // textBoxPressure1
            // 
            this.textBoxPressure1.Location = new System.Drawing.Point(761, 34);
            this.textBoxPressure1.Margin = new System.Windows.Forms.Padding(4);
            this.textBoxPressure1.Name = "textBoxPressure1";
            this.textBoxPressure1.Size = new System.Drawing.Size(115, 25);
            this.textBoxPressure1.TabIndex = 5;
            this.textBoxPressure1.KeyDown += new System.Windows.Forms.KeyEventHandler(this.TextBoxPressure_KeyDown);
            // 
            // labelPressure1Value
            // 
            this.labelPressure1Value.AutoSize = true;
            this.labelPressure1Value.Location = new System.Drawing.Point(767, 81);
            this.labelPressure1Value.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.labelPressure1Value.Name = "labelPressure1Value";
            this.labelPressure1Value.Size = new System.Drawing.Size(0, 15);
            this.labelPressure1Value.TabIndex = 8;
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(619, 81);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(130, 15);
            this.label1.TabIndex = 10;
            this.label1.Text = "实时正压（mBar):";
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(637, 231);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(67, 15);
            this.label2.TabIndex = 11;
            this.label2.Text = "占空比：";
            // 
            // textBox_DutyRatio
            // 
            this.textBox_DutyRatio.Location = new System.Drawing.Point(724, 228);
            this.textBox_DutyRatio.Name = "textBox_DutyRatio";
            this.textBox_DutyRatio.Size = new System.Drawing.Size(100, 25);
            this.textBox_DutyRatio.TabIndex = 12;
            this.textBox_DutyRatio.Text = "0.5";
            this.textBox_DutyRatio.KeyDown += new System.Windows.Forms.KeyEventHandler(this.textBox_DutyRatio_KeyDown);
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(622, 194);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(82, 15);
            this.label3.TabIndex = 13;
            this.label3.Text = "开关频率：";
            // 
            // textBox_freq
            // 
            this.textBox_freq.Location = new System.Drawing.Point(724, 191);
            this.textBox_freq.Name = "textBox_freq";
            this.textBox_freq.Size = new System.Drawing.Size(100, 25);
            this.textBox_freq.TabIndex = 14;
            this.textBox_freq.Text = "1";
            this.textBox_freq.KeyDown += new System.Windows.Forms.KeyEventHandler(this.textBox_freq_KeyDown);
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.Location = new System.Drawing.Point(619, 142);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(67, 15);
            this.label4.TabIndex = 15;
            this.label4.Text = "电池阀：";
            // 
            // label_ValveIndex
            // 
            this.label_ValveIndex.AutoSize = true;
            this.label_ValveIndex.Location = new System.Drawing.Point(1191, 263);
            this.label_ValveIndex.Name = "label_ValveIndex";
            this.label_ValveIndex.Size = new System.Drawing.Size(87, 15);
            this.label_ValveIndex.TabIndex = 16;
            this.label_ValveIndex.Text = "          ";
            // 
            // label5
            // 
            this.label5.AutoSize = true;
            this.label5.Location = new System.Drawing.Point(24, 34);
            this.label5.Name = "label5";
            this.label5.Size = new System.Drawing.Size(136, 15);
            this.label5.TabIndex = 17;
            this.label5.Text = "CO2浓度（设定）：";
            this.label5.Click += new System.EventHandler(this.label5_Click);
            // 
            // textBox1
            // 
            this.textBox1.Location = new System.Drawing.Point(166, 30);
            this.textBox1.Name = "textBox1";
            this.textBox1.Size = new System.Drawing.Size(100, 25);
            this.textBox1.TabIndex = 18;
            // 
            // groupBox1
            // 
            this.groupBox1.Controls.Add(this.dataGridView1);
            this.groupBox1.Controls.Add(this.labelPressure1);
            this.groupBox1.Controls.Add(this.labelPressure1Value);
            this.groupBox1.Controls.Add(this.textBoxPressure1);
            this.groupBox1.Controls.Add(this.label1);
            this.groupBox1.Controls.Add(this.textBox_freq);
            this.groupBox1.Controls.Add(this.label4);
            this.groupBox1.Controls.Add(this.label3);
            this.groupBox1.Controls.Add(this.textBox_DutyRatio);
            this.groupBox1.Controls.Add(this.label2);
            this.groupBox1.Location = new System.Drawing.Point(27, 37);
            this.groupBox1.Name = "groupBox1";
            this.groupBox1.Size = new System.Drawing.Size(938, 762);
            this.groupBox1.TabIndex = 20;
            this.groupBox1.TabStop = false;
            this.groupBox1.Text = "驱动气路控制";
            this.groupBox1.Enter += new System.EventHandler(this.groupBox1_Enter);
            // 
            // groupBox2
            // 
            this.groupBox2.Controls.Add(this.label12);
            this.groupBox2.Controls.Add(this.label11);
            this.groupBox2.Controls.Add(this.label10);
            this.groupBox2.Controls.Add(this.label9);
            this.groupBox2.Controls.Add(this.textBox2);
            this.groupBox2.Controls.Add(this.label6);
            this.groupBox2.Controls.Add(this.label5);
            this.groupBox2.Controls.Add(this.textBox1);
            this.groupBox2.Location = new System.Drawing.Point(1029, 39);
            this.groupBox2.Name = "groupBox2";
            this.groupBox2.Size = new System.Drawing.Size(522, 130);
            this.groupBox2.TabIndex = 21;
            this.groupBox2.TabStop = false;
            this.groupBox2.Text = "CO2/O2浓度（%）";
            // 
            // label12
            // 
            this.label12.AutoSize = true;
            this.label12.Location = new System.Drawing.Point(433, 76);
            this.label12.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label12.Name = "label12";
            this.label12.Size = new System.Drawing.Size(0, 15);
            this.label12.TabIndex = 23;
            // 
            // label11
            // 
            this.label11.AutoSize = true;
            this.label11.Location = new System.Drawing.Point(433, 32);
            this.label11.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label11.Name = "label11";
            this.label11.Size = new System.Drawing.Size(0, 15);
            this.label11.TabIndex = 16;
            // 
            // label10
            // 
            this.label10.AutoSize = true;
            this.label10.Location = new System.Drawing.Point(290, 75);
            this.label10.Name = "label10";
            this.label10.Size = new System.Drawing.Size(128, 15);
            this.label10.TabIndex = 22;
            this.label10.Text = "O2浓度（实测）：";
            // 
            // label9
            // 
            this.label9.AutoSize = true;
            this.label9.Location = new System.Drawing.Point(290, 34);
            this.label9.Name = "label9";
            this.label9.Size = new System.Drawing.Size(136, 15);
            this.label9.TabIndex = 21;
            this.label9.Text = "CO2浓度（实测）：";
            // 
            // textBox2
            // 
            this.textBox2.Location = new System.Drawing.Point(165, 66);
            this.textBox2.Name = "textBox2";
            this.textBox2.Size = new System.Drawing.Size(100, 25);
            this.textBox2.TabIndex = 20;
            // 
            // label6
            // 
            this.label6.AutoSize = true;
            this.label6.Location = new System.Drawing.Point(24, 75);
            this.label6.Name = "label6";
            this.label6.Size = new System.Drawing.Size(128, 15);
            this.label6.TabIndex = 19;
            this.label6.Text = "O2浓度（设定）：";
            // 
            // groupBox3
            // 
            this.groupBox3.Controls.Add(this.textBox_Lid_temperature);
            this.groupBox3.Controls.Add(this.label13);
            this.groupBox3.Controls.Add(this.label14);
            this.groupBox3.Controls.Add(this.label8);
            this.groupBox3.Controls.Add(this.label_Lid_temperature);
            this.groupBox3.Location = new System.Drawing.Point(1029, 228);
            this.groupBox3.Name = "groupBox3";
            this.groupBox3.Size = new System.Drawing.Size(522, 111);
            this.groupBox3.TabIndex = 22;
            this.groupBox3.TabStop = false;
            this.groupBox3.Text = "温度控制（℃）";
            // 
            // textBox_Lid_temperature
            // 
            this.textBox_Lid_temperature.Location = new System.Drawing.Point(173, 29);
            this.textBox_Lid_temperature.Name = "textBox_Lid_temperature";
            this.textBox_Lid_temperature.Size = new System.Drawing.Size(100, 25);
            this.textBox_Lid_temperature.TabIndex = 28;
            this.textBox_Lid_temperature.KeyDown += new System.Windows.Forms.KeyEventHandler(this.textBox_Lid_temperature_KeyDown);
            // 
            // label13
            // 
            this.label13.AutoSize = true;
            this.label13.Location = new System.Drawing.Point(433, 72);
            this.label13.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label13.Name = "label13";
            this.label13.Size = new System.Drawing.Size(0, 15);
            this.label13.TabIndex = 27;
            // 
            // label14
            // 
            this.label14.AutoSize = true;
            this.label14.Location = new System.Drawing.Point(433, 28);
            this.label14.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label14.Name = "label14";
            this.label14.Size = new System.Drawing.Size(0, 15);
            this.label14.TabIndex = 24;
            // 
            // label8
            // 
            this.label8.AutoSize = true;
            this.label8.Location = new System.Drawing.Point(24, 34);
            this.label8.Name = "label8";
            this.label8.Size = new System.Drawing.Size(112, 15);
            this.label8.TabIndex = 17;
            this.label8.Text = "温度（设定）：";
            this.label8.Click += new System.EventHandler(this.label8_Click);
            // 
            // label_Lid_temperature
            // 
            this.label_Lid_temperature.AutoSize = true;
            this.label_Lid_temperature.Location = new System.Drawing.Point(290, 30);
            this.label_Lid_temperature.Name = "label_Lid_temperature";
            this.label_Lid_temperature.Size = new System.Drawing.Size(112, 15);
            this.label_Lid_temperature.TabIndex = 25;
            this.label_Lid_temperature.Text = "温度（实测）：";
            // 
            // Form1
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(8F, 15F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1563, 843);
            this.Controls.Add(this.groupBox3);
            this.Controls.Add(this.groupBox2);
            this.Controls.Add(this.groupBox1);
            this.Controls.Add(this.label_ValveIndex);
            this.Controls.Add(this.button_stop);
            this.Controls.Add(this.button_start);
            this.Controls.Add(this.radioButtonConnect);
            this.Margin = new System.Windows.Forms.Padding(4);
            this.Name = "Form1";
            this.Text = "培养模块控制软件";
            ((System.ComponentModel.ISupportInitialize)(this.dataGridView1)).EndInit();
            this.groupBox1.ResumeLayout(false);
            this.groupBox1.PerformLayout();
            this.groupBox2.ResumeLayout(false);
            this.groupBox2.PerformLayout();
            this.groupBox3.ResumeLayout(false);
            this.groupBox3.PerformLayout();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.RadioButton radioButtonConnect;
        private System.Windows.Forms.DataGridView dataGridView1;
        private System.Windows.Forms.Button button_start;
        private System.Windows.Forms.Button button_stop;
        private System.Windows.Forms.Label labelPressure1;
        private System.Windows.Forms.TextBox textBoxPressure1;
        private System.Windows.Forms.Label labelPressure1Value;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.TextBox textBox_DutyRatio;
        private System.Windows.Forms.DataGridViewTextBoxColumn index;
        private System.Windows.Forms.DataGridViewTextBoxColumn freq;
        private System.Windows.Forms.DataGridViewTextBoxColumn DutyRatio;
        private System.Windows.Forms.DataGridViewCheckBoxColumn status;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.TextBox textBox_freq;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Label label_ValveIndex;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.TextBox textBox1;
        private System.Windows.Forms.GroupBox groupBox1;
        private System.Windows.Forms.GroupBox groupBox2;
        private System.Windows.Forms.TextBox textBox2;
        private System.Windows.Forms.Label label6;
        private System.Windows.Forms.GroupBox groupBox3;
        private System.Windows.Forms.Label label8;
        private System.Windows.Forms.Label label12;
        private System.Windows.Forms.Label label11;
        private System.Windows.Forms.Label label10;
        private System.Windows.Forms.Label label9;
        private System.Windows.Forms.Label label13;
        private System.Windows.Forms.Label label14;
        private System.Windows.Forms.Label label_Lid_temperature;
        private System.Windows.Forms.TextBox textBox_Lid_temperature;
    }
}

