'========================================================================
'  JRA-VAN Data Lab. �T���v���v���O�����P(Form1.vb)
'
'
'   �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
'
'========================================================================
'   (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
'========================================================================

Public Class frmMain
    Inherits System.Windows.Forms.Form


#Region " Windows �t�H�[�� �f�U�C�i�Ő������ꂽ�R�[�h "

    Public Sub New()
        MyBase.New()

        ' ���̌Ăяo���� Windows �t�H�[�� �f�U�C�i�ŕK�v�ł��B
        InitializeComponent()

        ' InitializeComponent() �Ăяo���̌�ɏ�������ǉ����܂��B

    End Sub

    ' Form �� dispose ���I�[�o�[���C�h���ăR���|�[�l���g�ꗗ���������܂��B
    Protected Overloads Overrides Sub Dispose(ByVal disposing As Boolean)
        If disposing Then
            If Not (components Is Nothing) Then
                components.Dispose()
            End If
        End If
        MyBase.Dispose(disposing)
    End Sub

    ' Windows �t�H�[�� �f�U�C�i�ŕK�v�ł��B
    Private components As System.ComponentModel.IContainer

    ' ���� : �ȉ��̃v���V�[�W���́AWindows �t�H�[�� �f�U�C�i�ŕK�v�ł��B
    ' Windows �t�H�[�� �f�U�C�i���g���ĕύX���Ă��������B  
    ' �R�[�h �G�f�B�^�͎g�p���Ȃ��ł��������B
    Friend WithEvents lblFileList As System.Windows.Forms.Label
    Friend WithEvents lblPrint As System.Windows.Forms.Label
    Friend WithEvents cmdJVSetUIProperties As System.Windows.Forms.Button
    Friend WithEvents cmdDelete As System.Windows.Forms.Button
    Friend WithEvents cmdJVLinkDialog As System.Windows.Forms.Button
    Friend WithEvents txtOut As System.Windows.Forms.RichTextBox
    Friend WithEvents txtFileList As System.Windows.Forms.RichTextBox
    Friend WithEvents cmdClear As System.Windows.Forms.Button
    Friend WithEvents AxJVLink1 As AxJVDTLabLib.AxJVLink

    <System.Diagnostics.DebuggerStepThrough()> Private Sub InitializeComponent()
        Dim resources As System.Resources.ResourceManager = New System.Resources.ResourceManager(GetType(frmMain))
        Me.lblFileList = New System.Windows.Forms.Label()
        Me.lblPrint = New System.Windows.Forms.Label()
        Me.cmdJVLinkDialog = New System.Windows.Forms.Button()
        Me.cmdJVSetUIProperties = New System.Windows.Forms.Button()
        Me.cmdDelete = New System.Windows.Forms.Button()
        Me.txtOut = New System.Windows.Forms.RichTextBox()
        Me.txtFileList = New System.Windows.Forms.RichTextBox()
        Me.cmdClear = New System.Windows.Forms.Button()
        Me.AxJVLink1 = New AxJVDTLabLib.AxJVLink()
        CType(Me.AxJVLink1, System.ComponentModel.ISupportInitialize).BeginInit()
        Me.SuspendLayout()
        '
        'lblFileList
        '
        Me.lblFileList.Location = New System.Drawing.Point(400, 96)
        Me.lblFileList.Name = "lblFileList"
        Me.lblFileList.Size = New System.Drawing.Size(128, 16)
        Me.lblFileList.TabIndex = 200
        Me.lblFileList.Text = "�Ǎ��݃t�@�C�����X�g"
        '
        'lblPrint
        '
        Me.lblPrint.Location = New System.Drawing.Point(16, 96)
        Me.lblPrint.Name = "lblPrint"
        Me.lblPrint.Size = New System.Drawing.Size(56, 16)
        Me.lblPrint.TabIndex = 198
        Me.lblPrint.Text = "�o��"
        '
        'cmdJVLinkDialog
        '
        Me.cmdJVLinkDialog.Location = New System.Drawing.Point(16, 16)
        Me.cmdJVLinkDialog.Name = "cmdJVLinkDialog"
        Me.cmdJVLinkDialog.Size = New System.Drawing.Size(88, 32)
        Me.cmdJVLinkDialog.TabIndex = 0
        Me.cmdJVLinkDialog.Text = "�f�[�^�捞��"
        '
        'cmdJVSetUIProperties
        '
        Me.cmdJVSetUIProperties.Location = New System.Drawing.Point(112, 16)
        Me.cmdJVSetUIProperties.Name = "cmdJVSetUIProperties"
        Me.cmdJVSetUIProperties.Size = New System.Drawing.Size(88, 32)
        Me.cmdJVSetUIProperties.TabIndex = 1
        Me.cmdJVSetUIProperties.Text = "JVLink�ݒ�"
        '
        'cmdDelete
        '
        Me.cmdDelete.Location = New System.Drawing.Point(208, 16)
        Me.cmdDelete.Name = "cmdDelete"
        Me.cmdDelete.Size = New System.Drawing.Size(88, 32)
        Me.cmdDelete.TabIndex = 2
        Me.cmdDelete.Text = "�t�@�C���폜"
        '
        'txtOut
        '
        Me.txtOut.Font = New System.Drawing.Font("�l�r �S�V�b�N", 9.0!, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, CType(128, Byte))
        Me.txtOut.Location = New System.Drawing.Point(16, 112)
        Me.txtOut.Name = "txtOut"
        Me.txtOut.RightMargin = 34000
        Me.txtOut.Size = New System.Drawing.Size(376, 336)
        Me.txtOut.TabIndex = 4
        Me.txtOut.Text = ""
        Me.txtOut.WordWrap = False
        '
        'txtFileList
        '
        Me.txtFileList.Font = New System.Drawing.Font("�l�r �S�V�b�N", 9.0!, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, CType(128, Byte))
        Me.txtFileList.Location = New System.Drawing.Point(400, 112)
        Me.txtFileList.Name = "txtFileList"
        Me.txtFileList.Size = New System.Drawing.Size(208, 336)
        Me.txtFileList.TabIndex = 5
        Me.txtFileList.Text = ""
        Me.txtFileList.WordWrap = False
        '
        'cmdClear
        '
        Me.cmdClear.Location = New System.Drawing.Point(304, 16)
        Me.cmdClear.Name = "cmdClear"
        Me.cmdClear.Size = New System.Drawing.Size(88, 32)
        Me.cmdClear.TabIndex = 3
        Me.cmdClear.Text = "�e�L�X�g�N���A"
        '
        'AxJVLink1
        '
        Me.AxJVLink1.Enabled = True
        Me.AxJVLink1.Location = New System.Drawing.Point(448, 16)
        Me.AxJVLink1.Name = "AxJVLink1"
        Me.AxJVLink1.OcxState = CType(resources.GetObject("AxJVLink1.OcxState"), System.Windows.Forms.AxHost.State)
        Me.AxJVLink1.Size = New System.Drawing.Size(72, 40)
        Me.AxJVLink1.TabIndex = 201
        '
        'frmMain
        '
        Me.AutoScaleBaseSize = New System.Drawing.Size(5, 12)
        Me.ClientSize = New System.Drawing.Size(626, 464)
        Me.Controls.AddRange(New System.Windows.Forms.Control() {Me.AxJVLink1, Me.cmdClear, Me.txtFileList, Me.txtOut, Me.cmdDelete, Me.cmdJVSetUIProperties, Me.cmdJVLinkDialog, Me.lblFileList, Me.lblPrint})
        Me.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedToolWindow
        Me.Name = "frmMain"
        Me.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        Me.Text = "Sample1 Main Form"
        CType(Me.AxJVLink1, System.ComponentModel.ISupportInitialize).EndInit()
        Me.ResumeLayout(False)

    End Sub

#End Region
    '------------------------------------------------------------------------------------------------
    '�@�@������
    '------------------------------------------------------------------------------------------------
    Private Sub frmMain_Load(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                                Handles MyBase.Load
        Try
            Dim sid As String                   ''���� JVInit:�\�t�g�E�F�AID
            Dim ReturnCode As String            ''�ߒl

            '�����ݒ�
            sid = "UNKNOWN"
            '***************
            'JVLink������
            '***************
            '������ JVInit�� JVLink���\�b�h�g�p�O(�A���AJVSetUIProPerties������)�Ɍďo��
            ReturnCode = AxJVLink1.JVInit(sid)

            '�G���[����
            If ReturnCode <> 0 Then     ''�G���[
                Call PrintOut("JVInit�G���[:" & ReturnCode & ControlChars.CrLf)
                '�I��
                Exit Sub
            Else                        ''����
                Call PrintOut("JVInit����I��:" & ReturnCode & ControlChars.CrLf)
            End If
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�f�[�^�捞�݃{�^���N���b�N���̏���
    '------------------------------------------------------------------------------------------------
    Private Sub cmdJVLinkDialog_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                        Handles cmdJVLinkDialog.Click
        Try
            'Form2�FJVLink�R���g���[���p�l�����J��
            Dim frmDialog As frmJVLinkDialog
            frmDialog = New frmJVLinkDialog()
            frmDialog.ShowDialog(Me)            ''�I�[�i�[�E�B���h�E�Ɏ���ʂ��w��

            frmDialog.Dispose()
            frmDialog = Nothing

            '�I��
            Exit Sub
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�u�o�́v�ɏ������ʂ�\��
    '------------------------------------------------------------------------------------------------
    Public Sub PrintOut(ByVal Message As String)
        Try
            'txtOut�ɕ������\��
            txtOut.AppendText(Message)
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub


    '------------------------------------------------------------------------------------------------
    '�@�@�u�t�@�C�����X�g�v�Ƀ_�E�����[�h�����t�@�C�����X�g��\��
    '------------------------------------------------------------------------------------------------
    Public Sub PrintFilelist(ByVal strMessage As String)
        Try
            'txtFileList�ɕ������\��
            txtFileList.AppendText(strMessage)
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@JVLink�ݒ�E�B���h�E�\��
    '------------------------------------------------------------------------------------------------
    Private Sub cmdJVSetUIProperties_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                    Handles cmdJVSetUIProperties.Click
        Try
            Dim ReturnCode As String            ''�ߒl

            '**********************
            'JVLink�ݒ��ʕ\��
            '**********************
            ReturnCode = AxJVLink1.JVSetUIProperties()

            '�G���[����
            If ReturnCode <> 0 Then         ''�G���[
                PrintOut("JVSetUIProperties�G���[:" & ReturnCode & ControlChars.CrLf)
            Else                            ''����
                PrintOut("JVSetUIProperties����I��:" & ReturnCode & ControlChars.CrLf)
            End If

            '�I��
            Exit Sub
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�w�肵���t�@�C�����폜
    '------------------------------------------------------------------------------------------------
    Private Sub cmdDelete_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                            Handles cmdDelete.Click
        Try
            Dim Message, Title, DefaultValue As String
            Dim MyValue As String
            Dim ReturnCode As String            ''�ߒl

            '�����l�ݒ�
            Message = "�t�@�C��������͂��ĉ�����"                          ''���b�Z�[�W
            Title = "�t�@�C���폜"                                          ''�^�C�g����
            DefaultValue = ""                                               ''�����l

            '�t�@�C��������
            MyValue = InputBox(Message, Title, DefaultValue)

            '**********************
            'JVFileDelete
            '**********************
            ReturnCode = AxJVLink1.JVFiledelete(MyValue)

            '�G���[����
            If ReturnCode <> 0 Then         ''�G���[
                PrintOut("JVFiledelete�G���[:" & ReturnCode & ControlChars.CrLf)
            Else                            ''����
                PrintOut("JVFiledelete����I��:" & ReturnCode & ControlChars.CrLf)
            End If

            '�I��
            Exit Sub
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�\�����N���A
    '------------------------------------------------------------------------------------------------
    Private Sub cmdClear_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                                Handles cmdClear.Click
        txtOut.Text = ""
        txtFileList.Text = ""
    End Sub

End Class
