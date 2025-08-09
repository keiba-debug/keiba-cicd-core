//========================================================================
//	JRA-VAN Data Lab. �T���v���v���O�����P(Unit1)
//
//
//	 �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//	 (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================

unit Unit1;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, StdCtrls, OleCtrls, JVDTLabLib_TLB, ComCtrls;

type
  TfrmMain = class(TForm)
	Label5: TLabel;
	Label6: TLabel;
	ButtonJVLinkDialog: TButton;
	ButtonJVSetUIProperties: TButton;
	ButtonDelete: TButton;
	JVLink1: TJVLink;
	ButtonClear: TButton;
	txtOut: TRichEdit;
	txtFilelist: TRichEdit;
	procedure ButtonJVLinkDialogClick(Sender: TObject);
	procedure ButtonJVSetUIPropertiesClick(Sender: TObject);
	procedure ButtonDeleteClick(Sender: TObject);
	procedure ButtonClearClick(Sender: TObject);
	procedure FormShow(Sender: TObject);

  private
	{ Private �錾 }

  public
	{ Public �錾 }
	procedure PrintOut(strMessage : WideString);
	procedure PrintFilelist(strMessage : WideString);
  end;

var
   frmMain: TfrmMain;

implementation

uses Unit2;

{$R *.dfm}

//------------------------------------------------------------------------------
//		������
//------------------------------------------------------------------------------
procedure TfrmMain.FormShow(Sender: TObject);
var
	sid : WideString;					//���� JVInit:�\�t�g�E�F�AID
	ReturnCode: Integer;
begin
	//�����ݒ�
	sid := 'UNKNOWN';

	//**********************
	//JVLink������
	//**********************
	//������ JVInit�� JVLink���\�b�h�g�p�O�i�A���AJVSetUIProPerties�������j�Ɍďo��
	ReturnCode := JVLink1.JVInit(sid);

	//�G���[����
	If ReturnCode <> 0 Then begin		//�G���[
		frmMain.PrintOut('JVInit�G���[:' + IntToStr(ReturnCode) + #13#10 );
		Exit;
		end
	else								//����
		frmMain.PrintOut('JVInit����I��:' + intToStr(ReturnCode) + #13#10 );
end;


//------------------------------------------------------------------------------
//		�f�[�^�捞�݃{�^���N���b�N���̏���
//------------------------------------------------------------------------------
procedure TfrmMain.ButtonJVLinkDialogClick(Sender: TObject);
var
	frmJVLinkDialog:TfrmJVLinkDialog;
begin
	frmJVLinkDialog := TfrmJVLinkDialog.Create(Self);
	//Form2:JVLink�_�C�A���O���J��
	frmJVLinkDialog.Showmodal;
	frmJVLinkDialog.Free;
	Exit;
end;

//------------------------------------------------------------------------------
//		�w�肵���t�@�C�����폜
//------------------------------------------------------------------------------
procedure TfrmMain.ButtonDeleteClick(Sender: TObject);
var
	MessageStr: WideString;
	Title: WideString;
	DefaultValue: WideString;
	MyValue: String;
	ReturnCode: Integer;
begin

	MessageStr := '�t�@�C��������͂��ĉ�����'; 			 //���b�Z�[�W
	Title := '�t�@�C���폜';								 //�^�C�g����
	DefaultValue := ''; 									 //�����l

	MyValue := InputBox(MessageStr, Title, DefaultValue);

	//**********************
	//JVFileDelete
	//**********************
	ReturnCode := JVLink1.JVFiledelete(MyValue);
	If ReturnCode <> 0 Then
		frmMain.PrintOut('JVFiledelete�G���[:' + IntToStr(Returncode) + #13#10 )
	Else
		frmMain.PrintOut('JVFiledelete����I��:' + IntToStr(Returncode) + #13#10 );

end;

//------------------------------------------------------------------------------
//�@�@JVLink�ݒ�E�B���h�E�\��
//------------------------------------------------------------------------------
procedure TfrmMain.ButtonJVSetUIPropertiesClick(Sender: TObject);
var
	ReturnCode: Integer;
begin
	//**********************
	//JVLink�ݒ��ʕ\��
	//**********************
	ReturnCode:=JVLink1.JVSetUIProperties();
	If ReturnCode <> 0 Then
		frmMain.PrintOut('JVSetUIProperties�G���[:' + IntToStr(Returncode) + #13#10 )
	Else
		frmMain.PrintOut('JVSetUIProperties����I��:' + IntToStr(Returncode) + #13#10 );

end;

//------------------------------------------------------------------------------
//		�u�o�́v�ɏ������ʂ�\��
//------------------------------------------------------------------------------
procedure TfrmMain.PrintOut(strMessage : WideString);
begin
	//txtOut�ɕ������\�����A���s����
	txtOut.SelStart:= txtOut.GetTextLen;
	txtOut.SelText:=strMessage;
	txtOut.Perform(EM_SCROLL, SB_PAGEDOWN, 0);
	Exit;
end;

//------------------------------------------------------------------------------
//		�u�t�@�C�����X�g�v�Ƀ_�E�����[�h�����t�@�C�����X�g��\��
//------------------------------------------------------------------------------
procedure TfrmMain.PrintFilelist(strMessage : WideString);
begin
	//txtFileList�ɕ������\�����A���s����
	txtFilelist.SelStart:= txtOut.GetTextLen;
	txtFilelist.SelText:=strMessage;
	txtFilelist.Perform(EM_SCROLL, SB_LINEDOWN, 0);

	Exit;
end;

//------------------------------------------------------------------------------
//		�\�����N���A
//------------------------------------------------------------------------------
procedure TfrmMain.ButtonClearClick(Sender: TObject);
begin
	txtOut.Text:='';
	txtFilelist.Text:='';
end;


end.


