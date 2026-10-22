// A small WinForms stand-in for a WINDEV app, used only by the Windows end-to-end test.
using System;
using System.IO;
using System.Windows.Forms;

static class FakeApp
{
    static string DataFile { get { return Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Clientes.fic"); } }

    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        var login = new Form { Text = "Acesso", Name = "WIN_Acesso", Width = 300, Height = 180 };
        var user = new TextBox { Left = 20, Top = 20, Width = 200, TabIndex = 0 };
        var password = new TextBox { Left = 20, Top = 50, Width = 200, TabIndex = 1, UseSystemPasswordChar = true };
        var ok = new Button { Text = "OK", Left = 20, Top = 85, TabIndex = 2 };
        ok.Click += delegate
        {
            if (user.Text != Environment.GetEnvironmentVariable("FAKE_EXPECTED_USER")) { MessageBox.Show("Utilizador inválido"); return; }
            login.Hide();
            var main = BuildMain();
            main.FormClosed += delegate { Application.Exit(); };
            main.Show();
        };
        login.Controls.AddRange(new Control[] { user, password, ok });
        login.AcceptButton = ok;
        Application.Run(login);
    }

    static Form BuildMain()
    {
        var main = new Form { Text = "Gestão Oficinas", Name = "WIN_MENU", Width = 500, Height = 300 };
        var menu = new MenuStrip();
        // Menu items deliberately have no Name: the crawler must match captions, as with WINDEV.
        var tabelas = new ToolStripMenuItem("Tabelas");
        var clientes = new ToolStripMenuItem("Clientes");
        clientes.Click += delegate { BuildClientes().Show(); };
        tabelas.DropDownItems.Add(clientes);
        var utilitarios = new ToolStripMenuItem("Utilitários");
        var rebuild = new ToolStripMenuItem("Reconstrução de Stocks");
        rebuild.Click += delegate { File.AppendAllText(DataFile, "rebuilt"); };
        utilitarios.DropDownItems.Add(rebuild);
        menu.Items.Add(tabelas);
        menu.Items.Add(utilitarios);
        var viaturas = new Button { Text = "Veículos", Name = "BTN_Viaturas", Left = 20, Top = 60, Width = 120 };
        viaturas.Click += delegate { BuildViaturas().Show(); };
        main.MainMenuStrip = menu;
        main.Controls.Add(viaturas);
        main.Controls.Add(menu);
        return main;
    }

    static Form BuildClientes()
    {
        var form = new Form { Text = "Clientes", Name = "WIN_Clientes", Width = 400, Height = 250 };
        var code = new TextBox { Left = 20, Top = 20, Width = 100, TabIndex = 0 };
        var name = new TextBox { Left = 20, Top = 50, Width = 250, TabIndex = 1 };
        var added = new Button { Text = "New", Left = 20, Top = 90, TabIndex = 2 };
        added.Click += delegate { BuildFicha().Show(); };
        form.Controls.AddRange(new Control[] { code, name, added });
        return form;
    }

    static Form BuildFicha()
    {
        var form = new Form { Text = "Ficha cliente", Name = "WIN_Ficha", Width = 300, Height = 200 };
        form.Controls.Add(new TextBox { Left = 20, Top = 20, Width = 200 });
        form.FormClosing += delegate(object sender, FormClosingEventArgs e)
        {
            if (MessageBox.Show("Cancelar ficha?", "Confirmar", MessageBoxButtons.YesNo) == DialogResult.No) e.Cancel = true;
        };
        return form;
    }

    static Form BuildViaturas()
    {
        // Looks harmless in the legacy code, but writes on open: the data guard must stop the run.
        var form = new Form { Text = "Veículos", Name = "WIN_Viaturas", Width = 300, Height = 200 };
        form.Load += delegate { File.AppendAllText(DataFile, "touched"); };
        form.Controls.Add(new ListBox { Left = 20, Top = 20, Width = 200 });
        return form;
    }
}
