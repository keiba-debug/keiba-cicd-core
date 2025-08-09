//========================================================================
//	JRA-VAN Data Lab. �T���v���v���O�����P(Sample1Dlg2.cpp)
//
//
//	 �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//	 (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================

#include "stdafx.h"
#include "sample1.h"
#include "sample1Dlg1.h"
#include "sample1Dlg2.h"

#include <comdef.h>

#ifdef _DEBUG
#define new DEBUG_NEW
#undef THIS_FILE
static char THIS_FILE[] = __FILE__;
#endif

const int JV_DATA_LARGEST_SIZE=110000;

/////////////////////////////////////////////////////////////////////////////
// CSample1Dlg2 �_�C�A���O

	extern CSample1Dlg1* m_pView;

	//�L�����Z���t���O
	bool DialogCancel;
	//���W�I�{�^��
	int m_iRadio;
	//JVOpen:���Ǎ��݃t�@�C����
    long ReadCount;                     
	//JVOpen:���_�E�����[�h�t�@�C����
    long DownloadCount;  

	//JVOpen:�^�C���X�^���v
	CString strLastFile;
	BSTR bstrLastFile;

CSample1Dlg2::CSample1Dlg2(CWnd* pParent /*=NULL*/)
	: CDialog(CSample1Dlg2::IDD, pParent)
{
	//{{AFX_DATA_INIT(CSample1Dlg2)
	m_iRadio = 0;
	//}}AFX_DATA_INIT
}


void CSample1Dlg2::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CSample1Dlg2)
	DDX_Control(pDX, IDC_PROGRESS2, m_pgrProgress2);
	DDX_Control(pDX, IDC_PROGRESS1, m_pgrProgress1);
	DDX_Control(pDX, IDC_EDIT2, m_txtFromDate);
	DDX_Control(pDX, IDC_EDIT1, m_txtDataSpec);
	DDX_Radio(pDX, IDC_RADIO1, m_iRadio);
	//}}AFX_DATA_MAP
}


BEGIN_MESSAGE_MAP(CSample1Dlg2, CDialog)
	//{{AFX_MSG_MAP(CSample1Dlg2)
	ON_BN_CLICKED(IDC_BUTTON1, OnButton1)
	ON_BN_CLICKED(IDC_BUTTON2, OnButton2)
	ON_WM_TIMER()
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

/////////////////////////////////////////////////////////////////////////////
// CSample1Dlg2 ���b�Z�[�W �n���h��

//------------------------------------------------------------------------------
//		�捞�݊J�n�{�^�����������Ƃ��̏���
//------------------------------------------------------------------------------
void CSample1Dlg2::OnButton1() 
{
		long ReturnCode;					//JVLink�߂�l
		CString DataSpec;
		CString FromDate;
		int DataOption;
	
		//�����l�ݒ�
		DialogCancel=false;					//�L�����Z���t���O������	
		m_pgrProgress1.SetPos(0);			//�v���O���X�o�[������
		m_pgrProgress2.SetPos(0);			//�v���O���X�o�[������
		
		m_pView->m_jvlink1.JVInit("UNKNOWN");

		m_iRadio=0;

		UpdateData(true);
		m_txtDataSpec.GetWindowText(DataSpec);
		m_txtFromDate.GetWindowText(FromDate);


		if (m_iRadio == 0)
			DataOption = 1;
		else if (m_iRadio == 1)
			DataOption = 2;
		else if (m_iRadio == 2)
			DataOption = 3;
	
		//**********************
		//JVLink�_�E�����[�h����
		//**********************
		ReturnCode = m_pView->m_jvlink1.JVOpen((LPCTSTR)DataSpec,
												(LPCTSTR)FromDate,
												DataOption,
												&ReadCount,
												&DownloadCount,
												&bstrLastFile);
		
		//�G���[����
		if (ReturnCode != 0) {		   //�G���[

			//������ɕϊ�
			CString strReturnCode;
			strReturnCode.Format("%d", ReturnCode);

			m_pView->PrintOut("JVOpen�G���[:" + strReturnCode + "\xd\xa" );

			//�I������
			JVClosing();

		}else{							//����

			//������ɕϊ�
			CString strReturnCode;
			CString strDownloadCount;
			CString strReadCount;
			strReturnCode.Format("%d", ReturnCode);
			strDownloadCount.Format("%d", DownloadCount);
			strReadCount.Format("%d", ReadCount);
			

			m_pView->PrintOut("JVOpen����I��:" + strReturnCode + "\xd\xa" );
			m_pView->PrintOut("ReadCount:" +
								strReadCount +
								", DownloadCount:" +
								strDownloadCount +
								"\xd\xa" );

			//���_�E�����[�h���`�F�b�N
			if (DownloadCount==0){							//���_�E�����[�h�����O
				//�v���O���X�o�[�P�O�O���\��
				m_pgrProgress1.SetRange(0,100);				//MAX���P�O�O�ɐݒ�
				m_pgrProgress1.SetPos(100);					//�v���O���X�o�[���P�O�O���\��
				//�Ǎ��ݏ���
				JVReading();
				//�I������
				JVClosing();
				return;
			}else{											//���_�E�����[�h�����O�ȏ�
					
				//�����ݒ�
				SetWindowText("�_�E�����[�h���E�E�E");
				m_pgrProgress1.SetRange(0,(short)DownloadCount);	//�v���O���X�o�[��MAX�l�ݒ�
				SetTimer(1,100,NULL);								//�^�C�}�[�N��
			}
		}
	
}

//------------------------------------------------------------------------------
//		�^�C�}�[�F�_�E�����[�h�i�������v���O���X�o�[�\��
//------------------------------------------------------------------------------
void CSample1Dlg2::OnTimer(UINT nIDEvent) 
{
		long ReturnCode;		//JVLink�߂�l

		//**********************
		//JVLink�_�E�����[�h�i����
		//**********************
		ReturnCode = m_pView->m_jvlink1.JVStatus();

		 //������ɕϊ�
			CString strReturnCode;
			CString strDownloadCount;
			strReturnCode.Format("%d", ReturnCode);
			strDownloadCount.Format("%d", DownloadCount);

		//�G���[����
		if (ReturnCode < 0 ){
				m_pView->PrintOut("JVStatus�G���[:" + strReturnCode + "\xd\xa" );
				//�^�C�}�[��~
				KillTimer(1);
				//�I������
				JVClosing();
				//�I��
				return;
		}else if (ReturnCode < DownloadCount ){
				//�v���O���X�o�[�\��
				SetWindowText("�_�E�����[�h���D�D�D("+ strReturnCode + "/" + strDownloadCount + ")");
				m_pgrProgress1.SetPos(ReturnCode);
		}else if (ReturnCode==DownloadCount){
				//�^�C�}�[��~
				KillTimer(1);
				//�v���O���X�o�[�\��
				SetWindowText("�_�E�����[�h���D�D�D("+ strReturnCode + "/" + strDownloadCount + ")");
				m_pgrProgress1.SetPos(ReturnCode);
				//�Ǎ��ݏ���
				JVReading();
				//�I������
				JVClosing();
		}
}

//------------------------------------------------------------------------------
//		�o�b�N�O���E���h����
//------------------------------------------------------------------------------
void CSample1Dlg2::PumpMessages()
{
		MSG msg;
		while (::PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
			   ::TranslateMessage(&msg);
			   ::DispatchMessage (&msg);
		}
}

//------------------------------------------------------------------------------
//		�Ǎ��ݏ���
//------------------------------------------------------------------------------
void CSample1Dlg2::JVReading()
{
		long	ReturnCode; 					//JVLink�߂�l
		long	BuffSize;						//�o�b�t�@�T�C�Y
		BuffSize = JV_DATA_LARGEST_SIZE;		//�o�b�t�@�T�C�Y�w��

		CString sBuff;							//�o�b�t�@
		CString sBuffName;						//�o�b�t�@��
		BSTR bBuff;								//JVRead �p�ǂݏo���o�b�t�@
		BSTR bBuffName;
		int JVReadingCount; 					//�Ǎ��݃t�@�C����

		variant_t varBuff;						//JVGets �p�ǂݏo���o�b�t�@�|�C���^
		char buff[JV_DATA_LARGEST_SIZE];		//JVGets �p�ǂݏo���e���|�����o�b�t�@
		HRESULT hr;
		SAFEARRAY *psa ;
		VARIANT *data;

		//�o�b�t�@�̈�m��
		bBuff=sBuff.AllocSysString();
		sBuffName.GetBuffer(32);
		bBuffName=sBuffName.AllocSysString();

		//������ɕϊ�
		CString strReadCount;
		strReadCount.Format("%d", ReadCount);

		//�����l
		ReturnCode=0;
		JVReadingCount=0;
		SetWindowText("�f�[�^�Ǎ��ݒ��D�D�D(0/" + strReadCount + ")");
		m_pgrProgress2.SetPos(0);
		m_pgrProgress2.SetRange(0,(int)ReadCount);

		do {

			PumpMessages();

				//�L�����Z���������ꂽ�珈���𔲂���
				if (DialogCancel==true) return;

				//***************
				//JVLink�Ǎ��ݏ���
				//***************

				// JVRead �ǂݍ��݊֐��Ăяo��
				//ReturnCode =  m_pView->m_jvlink1.JVRead(&bBuff,&BuffSize,&bBuffName);
				
				// JVGets �ǂݍ��݊֐��Ăяo��
				ReturnCode =  m_pView->m_jvlink1.JVGets(&varBuff,BuffSize,&bBuffName);

				//������ɕϊ�
				CString strReturnCode;
				CString strJVReadingCount;

				strReturnCode.Format("%d", ReturnCode);
				strJVReadingCount.Format("%d", JVReadingCount);
				
				//�G���[����
				if (ReturnCode > 0){		   //����I��

					// JVRead������ɏI�������ꍇ�̓o�b�t�@�[�̓��e����ʂɕ\�����܂��B
					// �T���v���v���O�����ł��邽�ߒP���ɑS�Ẵf�[�^��\�����Ă��܂����A��ʕ\��
					// �͎��Ԃ̂����鏈���ł��邽�ߓǂݍ��ݏ����S�̂̎��s���Ԃ��x���Ȃ��Ă��܂��B
					// �K�v�ɉ����ĉ���4�s���R�����g�A�E�g���邩���̏����ɒu�������Ă��������B

					// JVGets�p�ǂݍ��݃��[�`�� START
					psa = varBuff.parray;
					// �z��ݒ�f�[�^�A�h���X
					hr = SafeArrayAccessData(psa, (LPVOID*)&data);
					if (FAILED(hr))break ;
					// �z�񐔐ݒ�
					memcpy(buff,data,ReturnCode );
					buff[ReturnCode] = '\0';
					SafeArrayUnaccessData(psa);
					sBuff= buff;
					//�N���A
					VariantClear(&varBuff);
					VariantClear(data);
					SafeArrayDestroy(psa);
					// JVGets�p�ǂݍ��݃��[�`�� END

					// JVRead�p�ǂݍ��݃��[�`�� START
					//sBuff.GetBufferSetLength(ReturnCode);
					//sBuff = bBuff;
					// JVRead�p�ǂݍ��݃��[�`�� END

					m_pView->PrintOut(sBuff);

				}else if (ReturnCode == -1){   //�t�@�C���̐؂��
					//�t�@�C�����\��
					sBuffName.GetBufferSetLength(32);
					sBuffName = bBuffName;
					m_pView->PrintFileList(sBuffName + "\xd\xa" );
					m_pView->PrintOut("Read File :"+ strReturnCode + "\xd\xa" );
					//�v���O���X�o�[�\��
					JVReadingCount=JVReadingCount++; //�J�E���g�A�b�v
					m_pgrProgress2.SetPos(JVReadingCount);
					SetWindowText("�f�[�^�Ǎ��ݒ��D�D�D(" + strJVReadingCount + "/" + strReadCount + ")");
				}else if (ReturnCode == 0){    //�S���R�[�h�Ǎ��ݏI��(EOF)
					m_pView->PrintOut("JVRead EndOfFile :" + strReturnCode + "\xd\xa" );
					SetWindowText("�f�[�^�Ǎ��݊���(" + strJVReadingCount + "/" + strReadCount + ")");
					//Repeat�𔲂���
					break;
				}else if (ReturnCode < -1 ){	//�Ǎ��݃G���[
					m_pView->PrintOut("JVRead�G���[:" + strReturnCode + "\xd\xa" );
					//Repeat�𔲂���
					break;
				}
		} while (1);
		//�o�b�t�@���
		::SysFreeString(bBuff);
		::SysFreeString(bBuffName);
		sBuff.Empty();
		sBuffName.Empty();
}

//------------------------------------------------------------------------------
//		�I������
//------------------------------------------------------------------------------
void CSample1Dlg2::JVClosing()
{
		long ReturnCode;		//JVLink�߂�l

		KillTimer(1);
		::SysFreeString(bstrLastFile);

		//***************
		//JVLink�I������
		//***************
		ReturnCode = m_pView->m_jvlink1.JVClose();

		//������ɕϊ�
		CString strReturnCode;
		strReturnCode.Format("%d", ReturnCode);

		//�G���[����
		if (ReturnCode != 0)			//�G���[
				m_pView->PrintOut("JVClose�G���[:" + strReturnCode + "\xd\xa" );
		else							//����
				m_pView->PrintOut("JVClose����I��:" + strReturnCode + "\xd\xa" );
}

//------------------------------------------------------------------------------
//		�L�����Z���{�^���N���b�N���̏���
//------------------------------------------------------------------------------
void CSample1Dlg2::OnButton2() 
{
		//�^�C�}�[���I������
		KillTimer(1);

		//***************
		//JVLink���~����
		//***************
		m_pView->m_jvlink1.JVCancel();

		//�L�����Z���t���O�����Ă�
		DialogCancel=true;

		//���b�Z�[�W�\��
		m_pView->PrintOut("JVCancel:�L�����Z������܂���\xd\xa");
		SetWindowText("JVCancel:�L�����Z������܂���");	
}
