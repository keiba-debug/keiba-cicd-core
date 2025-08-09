//========================================================================
//  JRA-VAN Data Lab. �T���v���v���O�����P(Unit2)
//
//
//   �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//   (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================
unit Unit2;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, ComCtrls, StdCtrls, ExtCtrls, OleCtrls, JVDTLabLib_TLB ;

type
    TfrmJVLinkDialog = class(TForm)
    ButtonCancel: TButton;
    ProgressBar1: TProgressBar;
    ProgressBar2: TProgressBar;
    Label1: TLabel;
    Label2: TLabel;
    Label3: TLabel;
    Label4: TLabel;
    txtDataSpec: TEdit;
    txtFromDate: TEdit;
    ButtonStart: TButton;
    GroupBox1: TGroupBox;
    rbtNormal: TRadioButton;
    rbtIsthisweek: TRadioButton;
    rbtSetup: TRadioButton;
    TimerJVStatus: TTimer;

    procedure ButtonCancelClick(Sender: TObject);
    procedure ButtonStartClick(Sender: TObject);
    procedure TimerJVStatusTimer(Sender: TObject);
    procedure FormShow(Sender: TObject);

  private
    { Private �錾 }
    procedure JVClosing();
    procedure JVReading();
  public
    { Public �錾 }

  end;

var
    frmJVLinkDialog: TfrmJVLinkDialog;
    DialogCancel : Boolean;             //�L�����Z���t���O
    ReadCount : Integer;                //JVOpen:���Ǎ��݃t�@�C����
    DownloadCount : Integer;            //JVOpen:���_�E�����[�h�t�@�C����
    LastFileTimeStamp : WideString;     //JVOpen:�Ō�Ƀ_�E�����[�h�����t�@�C���̃^�C���X�^���v

implementation

uses Unit1;

{$R *.dfm}

//------------------------------------------------------------------------------
//      ��������
//------------------------------------------------------------------------------
procedure TfrmJVLinkDialog.FormShow(Sender: TObject);
begin
    // �E�B���h�E����ɍŏ�ʂɕ\������
    SetWindowPos(Handle, HWND_TOPMOST, 0, 0, 0, 0,
    SWP_NOMOVE or SWP_NOSIZE or SWP_NOACTIVATE);
end;

//------------------------------------------------------------------------------
//      �f�[�^�擾���s�{�^���N���b�N���̏���
//------------------------------------------------------------------------------
procedure TfrmJVLinkDialog.ButtonStartClick(Sender: TObject);
var
    DataSpec : WideString;
    FromDate : WideString;
    DataOption : Integer;
    ReturnCode  : Integer;              //JVLink�Ԓl
begin
    TimerJVStatus.Enabled:=false;       //�^�C�}�[��~
    DialogCancel:=false;                //�L�����Z���t���O������
    ProgressBar1.Position:=0;           //�v���O���X�o�[������
    ProgressBar2.Position:=0;
    //�����ݒ�

    DataSpec := txtDataSpec.Text;       //���� �t�@�C�����ʎq
    FromDate := txtFromDate.text;       //���� �f�[�^�񋟓��tFROM

    if rbtNormal.Checked=true then
        DataOption:=1
    else if rbtIsthisweek.Checked=true then
        DataOption:=2
    else if rbtSetup.Checked=true then
        DataOption:=3;

    Cursor:=crAppStart;

    //**********************
    //JVLink�_�E�����[�h����
    //**********************
    ReturnCode := frmMain.JVLink1.JVOpen(DataSpec,
                                         FromDate,
                                         DataOption,
                                         ReadCount,
                                         DownloadCount,
                                         LastFileTimeStamp);

        //�G���[����
    If ReturnCode <> 0 Then begin       //�G���[
        frmMain.PrintOut('JVOpen�G���[:' + IntToStr(ReturnCode) + #13#10 );
        //�I������
        JVClosing;
        end
    Else begin                          //����
        frmMain.PrintOut('JVOpen����I��:' + IntToStr(ReturnCode) + #13#10 );
        frmMain.PrintOut('ReadCount:' +
                           IntToStr(ReadCount) +
                           ', DownloadCount:' +
                           IntToStr(DownloadCount) +
                           #13#10 );
        //���_�E�����[�h���`�F�b�N
        If DownloadCount=0 then begin         //���_�E�����[�h�����O
            //�v���O���X�o�[�P�O�O���\��
            ProgressBar1.max:=100;                       //MAX���P�O�O�ɐݒ�
            ProgressBar1.Position:=ProgressBar1.Max;     //�v���O���X�o�[���P�O�O���\��
            //�Ǎ��ݏ���
            JVReading();
            //�I������
            JVClosing();
            end
        else begin                           //���_�E�����[�h�����O�ȏ�
            //�����ݒ�
            Caption:='�_�E�����[�h���E�E�E';
            ProgressBar1.Max:=DownloadCount;            //�v���O���X�o�[��MAX�l�ݒ�
            TimerJVStatus.Enabled := true;              //�^�C�}�[�N��
        end;
    end;

    //�I��
    Exit;
end;

//------------------------------------------------------------------------------
//      �^�C�}�[�F�_�E�����[�h�i�������v���O���X�o�[�\��
//------------------------------------------------------------------------------
procedure TfrmJVLinkDialog.TimerJVStatusTimer(Sender: TObject);
var
    ReturnCode  : Integer;              //JVLink�Ԓl
begin
    //**********************
    //JVLink�_�E�����[�h�i����
    //**********************
        ReturnCode :=  frmMain.JVLink1.JVStatus;

    //�G���[����
    If ReturnCode < 0 Then begin
        frmMain.PrintOut('JVStatus�G���[:' + IntToStr(ReturnCode) + #13#10 );
        //�^�C�}�[��~
        TimerJVStatus.Enabled:=false;
        //�I������
        JVClosing;
        //�I��
        Exit;
        end
    Else If ReturnCode<DownloadCount then begin
        //�v���O���X�o�[�\��
        Caption :='�_�E�����[�h���D�D�D('+ IntToStr(ReturnCode) + '/' + IntToStr(DownloadCount) + ')';
        ProgressBar1.Position:=ReturnCode;
        end
    Else If ReturnCode=DownloadCount then begin
        //�^�C�}�[��~
        TimerJVStatus.Enabled:=false;
        //�v���O���X�o�[�\��
        Caption :='�_�E�����[�h���D�D�D('+ IntToStr(ReturnCode) + '/' + IntToStr(DownloadCount) + ')';
        ProgressBar1.Position:= ReturnCode;
        //�Ǎ��ݏ���
        JVReading;
        //�I������
        JVClosing;
        //�I��
        Exit;
    end;
end;


//------------------------------------------------------------------------------
//      �Ǎ��ݏ���
//------------------------------------------------------------------------------
procedure TfrmJVLinkDialog.JVReading();
var
    BuffAnsi : AnsiString;              //�o�b�t�@
    BuffSize : Integer;             //�o�b�t�@�T�C�Y
    BuffName : WideString;          //�o�b�t�@��
    JVReadingCount : Integer;       //�Ǎ��݃t�@�C����
    ReturnCode  : Integer;              //JVLink�Ԓl
    BuffVar : OleVariant;
    P: Pointer;
begin
    //�����l
    JVReadingCount:=0;
    Caption := '�f�[�^�Ǎ��ݒ��D�D�D(0/' + IntToStr(ReadCount) + ')';
    ProgressBar2.Position := 0;
    ProgressBar2.Max:=ReadCount;
    //�o�b�t�@�̈�m��
    BuffSize := 110000;

    while True do begin


        //�o�b�N�O���E���h�ł̏���
        Application.ProcessMessages;
    	BuffVar := VarArrayCreate([0, 0],varByte);

        //�L�����Z���������ꂽ�珈���𔲂���
        if DialogCancel=true then exit;

            //***************
            //JVLink�Ǎ��ݏ���
            //***************
//            ReturnCode :=  frmMain.JVLink1.JVRead(Buff, BuffSize, BuffName);
            ReturnCode :=  frmMain.JVLink1.JVGets(BuffVar, BuffSize, BuffName);
            //�G���[����
            if ReturnCode > 0 then begin          //����I��

                // JVRead������ɏI�������ꍇ�̓o�b�t�@�[�̓��e����ʂɕ\�����܂��B
                // �T���v���v���O�����ł��邽�ߒP���ɑS�Ẵf�[�^��\�����Ă��܂����A��ʕ\��
                // �͎��Ԃ̂����鏈���ł��邽�ߓǂݍ��ݏ����S�̂̎��s���Ԃ��x���Ȃ��Ă��܂��B
                // �K�v�ɉ����ĉ��̂P�s���R�����g�A�E�g���邩���̏����ɒu�������Ă��������B

                SetLength(BuffAnsi, ReturnCode);
                P := VarArrayLock(BuffVar);
                try
                   Move(P^, BuffAnsi[1], ReturnCode);
                finally
                   VarArrayUnlock(BuffVar);
                   VarClear(BuffVar);
               end;
                frmMain.PrintOut(BuffAnsi);

                end
            else if ReturnCode = -1 then begin    //�t�@�C���̐؂��
                //�t�@�C�����\��
                frmMain.PrintFilelist(BuffName + #13#10 );
                frmMain.PrintOut('Read File:'+ IntToStr(ReturnCode) + #13#10 );
                //�v���O���X�o�[�\��
                JVReadingCount:=JVReadingCount+1; //�J�E���g�A�b�v
                ProgressBar2.Position:=JVReadingCount;
                Caption := '�f�[�^�Ǎ��ݒ��D�D�D(' + IntToStr(JVReadingCount) + '/' + IntToStr(ReadCount) + ')';
                end

            else if ReturnCode = 0 then begin     //�S���R�[�h�Ǎ��ݏI��(EOF)
                frmMain.PrintOut('JVRead EndOfFile :' + IntToStr(ReturnCode) + #13#10 );
                Caption := '�f�[�^�Ǎ��݊���(' + IntToStr(JVReadingCount) + '/' + IntToStr(ReadCount) + ')';
                //Repeat�𔲂���
                Break;
                end
            else if ReturnCode < -1 then begin    //�Ǎ��݃G���[
                frmMain.PrintOut('JVRead�G���[:' + IntToStr(ReturnCode) + #13#10 );
                //Repeat�𔲂���
                Break;
                end;

    end;

    Exit;

end;

//------------------------------------------------------------------------------
//      �L�����Z���{�^���N���b�N���̏���
//------------------------------------------------------------------------------
procedure TfrmJVLinkDialog.ButtonCancelClick(Sender: TObject);
begin
    //�^�C�}�[���I������
    TimerJVStatus.Enabled := False;

    //***************
    //JVLink���~����
    //***************
     frmMain.JVLink1.JVCancel();

    //�L�����Z���t���O�����Ă�
    DialogCancel:=true;

    //���b�Z�[�W�\��
    frmMain.PrintOut('JVCancel:�L�����Z������܂���' + #13#10 );
    Caption := 'JVCancel:�L�����Z������܂���';

    Exit;
end;

//------------------------------------------------------------------------------
//      �I������
//------------------------------------------------------------------------------
procedure TfrmJVLinkDialog.JVClosing();
var
    ReturnCode  : Integer;              //JVLink�Ԓl
begin

    //***************
    //JVLink�I������
    //***************
    ReturnCode :=  frmMain.JVLink1.JVClose;

    Cursor:=crDefault;

    //�G���[����
    If ReturnCode <> 0 Then     //�G���[
        frmMain.PrintOut('JVClose�G���[:' + IntToStr(ReturnCode) + #13#10 )
    Else                        //����
        frmMain.PrintOut('JVClose����I��:' + IntToStr(ReturnCode) + #13#10 );

    Exit;
end;

end.
