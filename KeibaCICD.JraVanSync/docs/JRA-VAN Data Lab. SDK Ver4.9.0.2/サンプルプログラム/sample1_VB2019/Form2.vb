'========================================================================
'  JRA-VAN Data Lab. �T���v���v���O�����P(Form2.vb)
'
'
'   �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
'
'========================================================================
'   (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
'========================================================================
Imports System
Imports System.Text

Public Class frmJVLinkDialog
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
    Friend WithEvents lblFromDate As System.Windows.Forms.Label
    Friend WithEvents lblDataSpec As System.Windows.Forms.Label
    Friend WithEvents tmrJVStatus As System.Windows.Forms.Timer
    Friend WithEvents cmdStart As System.Windows.Forms.Button
    Friend WithEvents lblProgressBar2 As System.Windows.Forms.Label
    Friend WithEvents lblProgressBar1 As System.Windows.Forms.Label
    Friend WithEvents progressBar2 As System.Windows.Forms.ProgressBar
    Friend WithEvents cmdCancel As System.Windows.Forms.Button
    Friend WithEvents progressBar1 As System.Windows.Forms.ProgressBar
    Friend WithEvents grpRadioBtn As System.Windows.Forms.GroupBox
    Friend WithEvents rbtSetup As System.Windows.Forms.RadioButton
    Friend WithEvents rbtNormal As System.Windows.Forms.RadioButton
    Friend WithEvents txtFromDate As System.Windows.Forms.TextBox
    Friend WithEvents txtDataSpec As System.Windows.Forms.TextBox
    Friend WithEvents rbtIsthisweek As System.Windows.Forms.RadioButton
    <System.Diagnostics.DebuggerStepThrough()> Private Sub InitializeComponent()
        Me.components = New System.ComponentModel.Container()
        Me.cmdStart = New System.Windows.Forms.Button()
        Me.lblProgressBar2 = New System.Windows.Forms.Label()
        Me.lblProgressBar1 = New System.Windows.Forms.Label()
        Me.progressBar2 = New System.Windows.Forms.ProgressBar()
        Me.cmdCancel = New System.Windows.Forms.Button()
        Me.progressBar1 = New System.Windows.Forms.ProgressBar()
        Me.tmrJVStatus = New System.Windows.Forms.Timer(Me.components)
        Me.grpRadioBtn = New System.Windows.Forms.GroupBox()
        Me.rbtSetup = New System.Windows.Forms.RadioButton()
        Me.rbtIsthisweek = New System.Windows.Forms.RadioButton()
        Me.rbtNormal = New System.Windows.Forms.RadioButton()
        Me.txtFromDate = New System.Windows.Forms.TextBox()
        Me.txtDataSpec = New System.Windows.Forms.TextBox()
        Me.lblFromDate = New System.Windows.Forms.Label()
        Me.lblDataSpec = New System.Windows.Forms.Label()
        Me.grpRadioBtn.SuspendLayout()
        Me.SuspendLayout()
        '
        'cmdStart
        '
        Me.cmdStart.Location = New System.Drawing.Point(392, 16)
        Me.cmdStart.Name = "cmdStart"
        Me.cmdStart.Size = New System.Drawing.Size(104, 32)
        Me.cmdStart.TabIndex = 5
        Me.cmdStart.Text = "�f�[�^�捞�݊J�n"
        '
        'lblProgressBar2
        '
        Me.lblProgressBar2.Location = New System.Drawing.Point(16, 152)
        Me.lblProgressBar2.Name = "lblProgressBar2"
        Me.lblProgressBar2.Size = New System.Drawing.Size(136, 16)
        Me.lblProgressBar2.TabIndex = 215
        Me.lblProgressBar2.Text = "�Ǎ���"
        '
        'lblProgressBar1
        '
        Me.lblProgressBar1.Location = New System.Drawing.Point(16, 112)
        Me.lblProgressBar1.Name = "lblProgressBar1"
        Me.lblProgressBar1.Size = New System.Drawing.Size(136, 16)
        Me.lblProgressBar1.TabIndex = 214
        Me.lblProgressBar1.Text = "�_�E�����[�h"
        '
        'progressBar2
        '
        Me.progressBar2.Location = New System.Drawing.Point(16, 168)
        Me.progressBar2.Name = "progressBar2"
        Me.progressBar2.Size = New System.Drawing.Size(352, 16)
        Me.progressBar2.TabIndex = 213
        '
        'cmdCancel
        '
        Me.cmdCancel.Location = New System.Drawing.Point(392, 56)
        Me.cmdCancel.Name = "cmdCancel"
        Me.cmdCancel.Size = New System.Drawing.Size(104, 32)
        Me.cmdCancel.TabIndex = 6
        Me.cmdCancel.Text = "�f�[�^�捞�ݒ��~"
        '
        'progressBar1
        '
        Me.progressBar1.Location = New System.Drawing.Point(16, 128)
        Me.progressBar1.Name = "progressBar1"
        Me.progressBar1.Size = New System.Drawing.Size(352, 16)
        Me.progressBar1.TabIndex = 211
        '
        'tmrJVStatus
        '
        Me.tmrJVStatus.Interval = 300
        '
        'grpRadioBtn
        '
        Me.grpRadioBtn.Controls.AddRange(New System.Windows.Forms.Control() {Me.rbtSetup, Me.rbtIsthisweek, Me.rbtNormal})
        Me.grpRadioBtn.Location = New System.Drawing.Point(16, 56)
        Me.grpRadioBtn.Name = "grpRadioBtn"
        Me.grpRadioBtn.Size = New System.Drawing.Size(352, 48)
        Me.grpRadioBtn.TabIndex = 223
        Me.grpRadioBtn.TabStop = False
        Me.grpRadioBtn.Tag = ""
        Me.grpRadioBtn.Text = "�擾�f�[�^"
        '
        'rbtSetup
        '
        Me.rbtSetup.Location = New System.Drawing.Point(200, 24)
        Me.rbtSetup.Name = "rbtSetup"
        Me.rbtSetup.Size = New System.Drawing.Size(104, 16)
        Me.rbtSetup.TabIndex = 4
        Me.rbtSetup.Tag = ""
        Me.rbtSetup.Text = "�Z�b�g�A�b�v�f�[�^"
        '
        'rbtIsthisweek
        '
        Me.rbtIsthisweek.Location = New System.Drawing.Point(88, 24)
        Me.rbtIsthisweek.Name = "rbtIsthisweek"
        Me.rbtIsthisweek.Size = New System.Drawing.Size(104, 16)
        Me.rbtIsthisweek.TabIndex = 3
        Me.rbtIsthisweek.Tag = ""
        Me.rbtIsthisweek.Text = "���T�J�Ãf�[�^"
        '
        'rbtNormal
        '
        Me.rbtNormal.Checked = True
        Me.rbtNormal.Location = New System.Drawing.Point(8, 24)
        Me.rbtNormal.Name = "rbtNormal"
        Me.rbtNormal.Size = New System.Drawing.Size(104, 16)
        Me.rbtNormal.TabIndex = 2
        Me.rbtNormal.TabStop = True
        Me.rbtNormal.Tag = ""
        Me.rbtNormal.Text = "�ʏ�f�[�^"
        '
        'txtFromDate
        '
        Me.txtFromDate.Location = New System.Drawing.Point(248, 32)
        Me.txtFromDate.Name = "txtFromDate"
        Me.txtFromDate.Size = New System.Drawing.Size(120, 19)
        Me.txtFromDate.TabIndex = 1
        Me.txtFromDate.Text = ""
        '
        'txtDataSpec
        '
        Me.txtDataSpec.Location = New System.Drawing.Point(16, 32)
        Me.txtDataSpec.Name = "txtDataSpec"
        Me.txtDataSpec.Size = New System.Drawing.Size(224, 19)
        Me.txtDataSpec.TabIndex = 0
        Me.txtDataSpec.Text = ""
        '
        'lblFromDate
        '
        Me.lblFromDate.Location = New System.Drawing.Point(248, 16)
        Me.lblFromDate.Name = "lblFromDate"
        Me.lblFromDate.Size = New System.Drawing.Size(120, 16)
        Me.lblFromDate.TabIndex = 222
        Me.lblFromDate.Text = "�f�[�^�񋟓�FROM"
        '
        'lblDataSpec
        '
        Me.lblDataSpec.Location = New System.Drawing.Point(16, 16)
        Me.lblDataSpec.Name = "lblDataSpec"
        Me.lblDataSpec.Size = New System.Drawing.Size(160, 16)
        Me.lblDataSpec.TabIndex = 221
        Me.lblDataSpec.Text = "�t�@�C�����ʎq"
        '
        'frmJVLinkDialog
        '
        Me.AutoScaleBaseSize = New System.Drawing.Size(5, 12)
        Me.ClientSize = New System.Drawing.Size(506, 198)
        Me.Controls.AddRange(New System.Windows.Forms.Control() {Me.grpRadioBtn, Me.txtFromDate, Me.txtDataSpec, Me.lblFromDate, Me.lblDataSpec, Me.cmdStart, Me.lblProgressBar2, Me.lblProgressBar1, Me.progressBar2, Me.cmdCancel, Me.progressBar1})
        Me.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedToolWindow
        Me.MaximizeBox = False
        Me.MinimizeBox = False
        Me.Name = "frmJVLinkDialog"
        Me.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        Me.Text = "Sample1 JVLink Dialog"
        Me.grpRadioBtn.ResumeLayout(False)
        Me.ResumeLayout(False)

    End Sub

#End Region

    Private frmOwner As frmMain                 ''���C���t�H�[��
    Private CancelFlag As Boolean               ''�L�����Z���t���O
    Private ReadCount As Integer                ''JVOpen:���Ǎ��݃t�@�C����
    Private DownloadCount As Integer            ''JVOpen:���_�E�����[�h�t�@�C����
    Private LastFileTimeStamp As String         ''JVOpen:�Ō�Ƀ_�E�����[�h�����t�@�C���̃^�C���X�^���v


    '------------------------------------------------------------------------------------------------
    '�@�@�f�[�^�擾���s�{�^���N���b�N���̏���
    '------------------------------------------------------------------------------------------------
    Private Sub cmdStart_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                                Handles cmdStart.Click
        Try

            Dim DataSpec As String              ''���� JVOpen:�t�@�C�����ʎq
            Dim FromDate As String              ''���� JVOpen:�f�[�^�񋟓��tFROM
            Dim DataOption As Integer           ''���� JVOpen:�I�v�V����
            Dim ReturnCode As Integer           ''JVLink�ߒl

            '�����l�ݒ�
            tmrJVStatus.Enabled = False         ''�^�C�}�[��~
            frmOwner = Owner                    ''�e�t�H�[�����w��
            CancelFlag = False                  ''�L�����Z���t���O������
            progressBar1.Value = 0              ''�v���O���X�o�[������
            progressBar2.Value = 0

            '�����ݒ�
            DataSpec = txtDataSpec.Text
            FromDate = txtFromDate.Text

            If rbtNormal.Checked = True Then
                DataOption = 1
            ElseIf rbtIsthisweek.Checked = True Then
                DataOption = 2
            ElseIf rbtSetup.Checked = True Then
                DataOption = 3
            End If

            Cursor = Cursors.AppStarting()

            '**********************
            'JVLink�_�E�����[�h����
            '**********************
            ReturnCode = frmOwner.AxJVLink1.JVOpen(DataSpec, _
                                             FromDate, _
                                             DataOption, _
                                             ReadCount, _
                                             DownloadCount, _
                                             LastFileTimeStamp)

            '�G���[����
            If ReturnCode <> 0 Then     ''�G���[
                Call frmOwner.PrintOut("JVOpen�G���[:" & ReturnCode & ControlChars.CrLf)
                '�I������
                Call JVClosing()
            Else                        ''����
                Call frmOwner.PrintOut("JVOpen����I��:" & ReturnCode & ControlChars.CrLf)
                Call frmOwner.PrintOut("ReadCount:" & _
                                        ReadCount & _
                                        " , DownloadCount:" & _
                                        DownloadCount & _
                                        ControlChars.CrLf)

                '���_�E�����[�h�����`�F�b�N
                If DownloadCount = 0 Then                       ''���_�E�����[�h��=�O
                    '�v���O���X�o�[100���\��
                    progressBar1.Maximum = 100                  ''MAX��100�ɐݒ�
                    progressBar1.Value = progressBar1.Maximum   ''�v���O���X�o�[100���\��
                    Text = "�_�E�����[�h����"
                    '�Ǎ��ݏ���
                    Call JVReading()
                    '�I������
                    Call JVClosing()
                Else                                            ''���_�E�����[�h�����O�ȏ�
                    '�����l�ݒ�
                    Text = "�_�E�����[�h���E�E�E"
                    progressBar1.Maximum = DownloadCount        ''�v���O���X�o�[�̂l�`�w�l�ݒ�
                    '�^�C�}�[�n���F�_�E�����[�h�i�������v���O���X�o�[�\��
                    tmrJVStatus.Enabled = True                  ''�_�E�����[�h�X�e�[�^�X���Ď�����
                End If
            End If

            '�I��
            Exit Sub

        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub


    '------------------------------------------------------------------------------------------------
    '�@�@�^�C�}�[�F�_�E�����[�h�󋵂��v���O���X�o�[�\��
    '------------------------------------------------------------------------------------------------
    Private Sub tmrJVStatus_Tick(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                            Handles tmrJVStatus.Tick
        Try
            Dim ReturnCode As Integer           ''JVLink�ߒl

            '**********************
            'JVLink�_�E�����[�h�i����
            '**********************
            ReturnCode = frmOwner.AxJVLink1.JVStatus                ''�_�E�����[�h�ς̃t�@�C������Ԃ�

            '�G���[����
            If ReturnCode < 0 Then                                  ''�G���[
                Call frmOwner.PrintOut("JVStatus�G���[:" & ReturnCode)
                '�^�C�}�[��~
                tmrJVStatus.Enabled = False
                '�I������
                Call JVClosing()
                '�I��
                Exit Sub
            ElseIf ReturnCode < DownloadCount Then                  ''�X�e�[�^�X
                '�v���O���X�\��
                Text = "�_�E�����[�h���D�D�D(" & ReturnCode & "/" & DownloadCount & ")"
                progressBar1.Value = ReturnCode
            ElseIf ReturnCode = DownloadCount Then                  ''�X�e�[�^�X100��
                '�^�C�}�[��~
                tmrJVStatus.Enabled = False
                '�v���O���X�\��
                Text = "�_�E�����[�h����(" & ReturnCode & "/" & DownloadCount & ")"
                progressBar1.Value = ReturnCode
                '�Ǎ��ݏ���
                Call JVReading()
                '�I������
                Call JVClosing()
                '�I��
                Exit Sub
            End If

        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�Ǎ����� 
    '------------------------------------------------------------------------------------------------
    Public Sub JVReading()
        Try
            Dim Buff As String                          ''�o�b�t�@
            Dim BuffSize As Integer                     ''�o�b�t�@�T�C�Y
            Dim BuffName As String                      ''�o�b�t�@��
            Dim JVReadingCount As Integer               ''�Ǎ��݃t�@�C����
            Dim ReturnCode As Integer                   ''JVLink�ߒl
            Dim bytData(0) As Byte                      ''JVGets�p�o�b�t�@�|�C���^

            '�����l�ݒ�
            progressBar2.Maximum = ReadCount
            JVReadingCount = 0
            progressBar2.Value = 0
            Text = "�f�[�^�Ǎ��ݒ��D�D�D(0/" & ReadCount & ")"

            '�o�b�t�@�̈�m��
            BuffSize = 110000
            Buff = New String(vbNullChar, BuffSize)
            BuffName = String.Empty

            Do
                '�o�b�N�O���E���h�ł̏���
                System.Windows.Forms.Application.DoEvents()

                '�L�����Z���������ꂽ�珈���𔲂���
                If CancelFlag = True Then Exit Sub

                '**********************
                'JVLink�Ǎ��ݏ���
                '**********************
                'ReturnCode = frmOwner.AxJVLink1.JVRead(Buff, BuffSize, BuffName)
#Disable Warning BC41999
                ReturnCode = frmOwner.AxJVLink1.JVGets(bytData, BuffSize, BuffName)
#Enable Warning BC41999
                '�G���[����
                Select Case ReturnCode
                    Case Is > 0      ''����

                        ' JVRead������ɏI�������ꍇ�̓o�b�t�@�[�̓��e����ʂɕ\�����܂��B
                        ' �T���v���v���O�����ł��邽�ߒP���ɑS�Ẵf�[�^��\�����Ă��܂����A��ʕ\��
                        ' �͎��Ԃ̂����鏈���ł��邽�ߓǂݍ��ݏ����S�̂̎��s���Ԃ��x���Ȃ��Ă��܂��B
                        ' �K�v�ɉ����ĉ��̂P�s���R�����g�A�E�g���邩���̏����ɒu�������Ă��������B
                        'Call frmOwner.PrintOut(Buff)
                        Call frmOwner.PrintOut(System.Text.Encoding.GetEncoding(932).GetString(bytData))
						ReDim bytData(0)

                    Case -1          ''�t�@�C���̐؂��
                        '�t�@�C�����\��
                        Call frmOwner.PrintFilelist(BuffName & ControlChars.CrLf)
                        Call frmOwner.PrintOut("JVRead File :" & ReturnCode & ControlChars.CrLf)
                        '�v���O���X�o�[�\��
                        JVReadingCount = JVReadingCount + 1 ''�J�E���g�A�b�v
                        progressBar2.Value = JVReadingCount
                        Text = "�f�[�^�Ǎ��ݒ��D�D�D(" & JVReadingCount & "/" & ReadCount & ")"
                    Case 0          ''�S���R�[�h�Ǎ��ݏI��(EOF)
                        Call frmOwner.PrintOut("JVRead EndOfFile :" & ReturnCode & ControlChars.CrLf)
                        Text = "�f�[�^�Ǎ��݊���(" & JVReadingCount & "/" & ReadCount & ")"
                        '�I��
                        Exit Sub
                    Case Is < -1     ''�G���[
                        Call frmOwner.PrintOut("JVRead�G���[:" & ReturnCode & ControlChars.CrLf)
                        '�I��
                        Exit Sub
                End Select

            Loop
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�L�����Z���{�^���N���b�N���̏���
    '------------------------------------------------------------------------------------------------
    Private Sub cmdCancel_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) _
                                                                            Handles cmdCancel.Click
        Try
            '�^�C�}�[��~
            tmrJVStatus.Enabled = False

            '***************
            'JVLink���~����
            '***************
            frmOwner.AxJVLink1.JVCancel()

            '�L�����Z���t���O�����Ă�
            CancelFlag = True

            Call frmOwner.PrintOut("JVCancel:�L�����Z������܂���" & ControlChars.CrLf)
            Text = "JVCancel:�L�����Z������܂���"

            '�I��
            Exit Sub
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

    '------------------------------------------------------------------------------------------------
    '�@�@�I������
    '------------------------------------------------------------------------------------------------
    Private Sub JVClosing()
        Try
            Dim ReturnCode As Integer           ''JVLink�ߒl

            '***************
            'JVLink�I������
            '***************
            ReturnCode = frmOwner.AxJVLink1.JVClose()

            Cursor = Cursors.Default()

            If ReturnCode <> 0 Then         ''�G���[
                Call frmOwner.PrintOut("JVClose�G���[:" & CStr(ReturnCode) & ControlChars.CrLf)
            Else                            ''����
                Call frmOwner.PrintOut("JVClose����I��:" & CStr(ReturnCode) & ControlChars.CrLf)
            End If

            '�I��
            Exit Sub
        Catch
            Debug.WriteLine(Err.Description)
        End Try
    End Sub

End Class
